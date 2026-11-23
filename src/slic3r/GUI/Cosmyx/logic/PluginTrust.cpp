#include "PluginTrust.hpp"

#include <algorithm>
#include <cctype>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <functional>
#include <ios>
#include <map>
#include <mutex>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include <boost/filesystem/operations.hpp>
#include <boost/filesystem/path.hpp>
#include <boost/nowide/fstream.hpp>
#include <boost/system/error_code.hpp>
#include <miniz.h>
#include <nlohmann/json.hpp>

#include "CloudServer.hpp"
#include "PluginSigning.hpp"
#include "libslic3r/AppConfig.hpp"
#include "libslic3r/miniz_extension.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace fs = boost::filesystem;
using nlohmann::json;

namespace {

// The stored pins document, {} when none is stored. False, with doc {}, when
// the stored value is not a JSON object (hand-edited or truncated).
bool read_trust_doc(const AppConfig& config, json& doc)
{
    const std::string text = config.get(PLUGIN_TRUST_KEY);
    doc                    = json::object();
    if (trim_value(text).empty())
        return true;
    json parsed = json::parse(text, nullptr, /*allow_exceptions=*/false);
    if (!parsed.is_object())
        return false;
    doc = std::move(parsed);
    return true;
}

std::mutex& pending_mutex()
{
    static std::mutex mutex;
    return mutex;
}

// (plugin id, SHA-256 hex) -> record of a package that passed the check. The
// plugin id is part of the key: two plugins may ship the same bytes.
using PendingKey = std::pair<std::string, std::string>;

std::map<PendingKey, PackageRecord>& pending_records()
{
    static std::map<PendingKey, PackageRecord> records;
    return records;
}

bool read_file(const fs::path& path, std::string& data)
{
    boost::nowide::ifstream file(path.string(), std::ios::binary);
    if (!file)
        return false;
    std::ostringstream content;
    content << file.rdbuf();
    data = content.str();
    return !file.bad();
}

} // namespace

std::string normalize_server_url(const std::string& url)
{
    ServerAddress address;
    return parse_server_address(url, address) ? address.url() : std::string();
}

ServerPins server_pins(const AppConfig& config, const std::string& server_url)
{
    ServerPins        pins;
    const std::string url = normalize_server_url(server_url);
    if (url.empty())
        return pins;
    json doc;
    read_trust_doc(config, doc); // an unreadable document holds no pins
    const auto entry = doc.find(url);
    if (entry == doc.end() || !entry->is_object())
        return pins;
    const auto key = entry->find("public_key");
    if (key != entry->end() && !key->is_null() && !(key->is_string() && trim_value(key->get<std::string>()).empty())) {
        // A pin that cannot be read refuses the server: no key and no opt-in.
        if (!key->is_string() || public_key_id(key->get<std::string>(), &pins.public_key).empty())
            return pins;
    }
    const auto allow = entry->find("allow_unverified");
    pins.allow_unverified = allow != entry->end() && allow->is_boolean() && allow->get<bool>();
    return pins;
}

bool set_server_pins(AppConfig& config, const std::string& server_url, const ServerPins& pins)
{
    std::string       key;
    const std::string url = normalize_server_url(server_url);
    if (url.empty() || (!trim_value(pins.public_key).empty() && public_key_id(pins.public_key, &key).empty()))
        return false;
    json doc;
    // Saving over an unreadable document would drop every other server's pins.
    if (!read_trust_doc(config, doc))
        return false;
    if (key.empty() && !pins.allow_unverified)
        doc.erase(url);
    else
        doc[url] = {{"public_key", key}, {"allow_unverified", pins.allow_unverified}};
    config.set(PLUGIN_TRUST_KEY, doc.dump());
    return true;
}

PinsSave pins_to_save(const std::string& loaded_url, const std::string& applied_url)
{
    if (server_kind(applied_url) != ServerKind::Custom)
        return PinsSave::None;
    const std::string applied = normalize_server_url(applied_url);
    return !applied.empty() && normalize_server_url(loaded_url) == applied ? PinsSave::Typed : PinsSave::Keep;
}

std::string public_key_id(const std::string& typed, std::string* normalized)
{
    std::string hex = trim_value(typed);
    std::transform(hex.begin(), hex.end(), hex.begin(), [](char c) { return static_cast<char>(std::tolower(static_cast<unsigned char>(c))); });
    std::string raw;
    if (!is_lower_hex(hex, 64) || !from_lower_hex(hex, raw))
        return {};
    if (normalized != nullptr)
        *normalized = hex;
    return key_id_of(raw);
}

ServerTrust server_trust(const AppConfig& config, const std::string& server_url)
{
    ServerTrust   trust;
    ServerAddress address;
    switch (server_kind(server_url, &address)) {
    case ServerKind::Unrecognised:
        // No pin of the user ever applies, and the build's keys neither.
        trust.unrecognised = true;
        return trust;
    case ServerKind::Cosmyx:
        trust.cosmyx_server = true;
        trust.keys          = built_in_keys();
        return trust;
    case ServerKind::Custom: break;
    }
    const ServerPins pins = server_pins(config, address.url());
    std::string      error;
    if (!pins.public_key.empty()) {
        std::string raw;
        from_lower_hex(pins.public_key, raw);
        add_pinned_key(trust.keys, key_id_of(raw), pins.public_key, error);
    }
    // A pinned key always means full verification, never a fallback.
    trust.allow_unverified = pins.public_key.empty() && pins.allow_unverified;
    return trust;
}

bool request_version(const std::string& requested, std::string& version)
{
    if (!requested.empty() && !is_strict_version(requested))
        return false;
    version = requested;
    return true;
}

PackageVerdict check_plugin_package(const json*          row,
                                    const std::string&   body,
                                    const ClientRequest& request,
                                    const ServerTrust&   trust,
                                    const KeyIdSet&      revoked,
                                    const std::string&   installed_version,
                                    bool                 allow_downgrade)
{
    PackageVerdict verdict;
    if (trust.unrecognised) {
        verdict.reason = SIGN_UNRECOGNISED_SERVER;
        return verdict;
    }
    if (row == nullptr) {
        verdict.reason = SIGN_NO_ROW;
        return verdict;
    }

    // Anti-rollback runs before the signature check: an old signed version
    // stays valid forever, so only the client can refuse it.
    if (!allow_downgrade && row->is_object()) {
        const auto version = row->find("version");
        if (version != row->end() && version->is_string() && is_downgrade(installed_version, version->get<std::string>())) {
            verdict.reason = SIGN_DOWNGRADE;
            return verdict;
        }
    }

    std::string key_id;
    if (!trust.keys.empty())
        verdict.reason = verify_package_row(*row, body, request, trust.keys, revoked, &key_id);
    else if (trust.allow_unverified && !trust.cosmyx_server)
        verdict.reason = check_unsigned_package_row(*row, body, request);
    else
        verdict.reason = SIGN_NO_PINNED_KEY;

    if (verdict.ok())
        verdict.record = {row->at("plugin_id").get<std::string>(), row->at("version").get<std::string>(),
                          row->at("sha256").get<std::string>(), static_cast<std::uint64_t>(body.size()), key_id};
    return verdict;
}

bool read_package_record(const fs::path& plugin_dir, PackageRecord& record)
{
    std::string text;
    return read_file(plugin_dir / PACKAGE_RECORD_FILE, text) && record_from_json(text, record);
}

bool write_package_record(const fs::path& plugin_dir, const PackageRecord& record, std::string& error)
{
    const fs::path target = plugin_dir / PACKAGE_RECORD_FILE;
    const fs::path temp   = plugin_dir / (std::string(PACKAGE_RECORD_FILE) + ".tmp");
    bool written = false;
    {
        boost::nowide::ofstream file(temp.string(), std::ios::binary | std::ios::trunc);
        const std::string       text = record_to_json(record);
        file.write(text.data(), static_cast<std::streamsize>(text.size()));
        file.close();
        written = !file.fail();
    }
    boost::system::error_code ec;
    if (written)
        fs::rename(temp, target, ec);
    if (!written || ec) {
        // A partly written temp file is never left behind (a folder in its
        // place is not ours to remove).
        boost::system::error_code remove_ec;
        if (!fs::is_directory(temp, remove_ec))
            fs::remove(temp, remove_ec);
        error = "cannot write " + target.string();
        return false;
    }
    return true;
}

void remember_checked_package(const PackageRecord& record)
{
    std::lock_guard<std::mutex> lock(pending_mutex());
    pending_records()[{record.plugin_id, record.sha256}] = record;
}

void forget_checked_packages(const std::string& plugin_id)
{
    std::lock_guard<std::mutex> lock(pending_mutex());
    auto&                       records = pending_records();
    for (auto it = records.lower_bound({plugin_id, std::string()}); it != records.end() && it->first.first == plugin_id;)
        it = records.erase(it);
}

// The upstream installer moves the replaced plugin folder aside and installs
// into a fresh one, so no wheel extraction of the replaced package is left in
// plugin_dir to remove here (decision 0204).
bool commit_package_record(const std::string&   plugin_id,
                           const fs::path&      plugin_dir,
                           const fs::path&      package_file,
                           std::string&         error,
                           const PackageRecord* floor)
{
    std::string   data;
    bool          found = false;
    PackageRecord record;
    if (read_file(package_file, data)) {
        std::lock_guard<std::mutex> lock(pending_mutex());
        auto&                       records = pending_records();
        const auto                  it      = records.find({plugin_id, sha256_hex(data)});
        if (it != records.end() && it->second.size == data.size()) {
            record = it->second;
            records.erase(it);
            found = true;
        }
    }
    if (found && write_package_record(plugin_dir, record, error))
        return true;
    if (!found)
        error = "the installed package is not the one whose signature was checked";
    refuse_installed_package(plugin_dir, package_file, floor);
    return false;
}

bool commit_checked_install(const std::string&                       plugin_id,
                            const fs::path&                          plugin_dir,
                            const fs::path&                          package_file,
                            const std::function<bool(std::string&)>& metadata_matches,
                            std::string&                             error,
                            const PackageRecord*                     floor)
{
    try {
        if (metadata_matches(error))
            return commit_package_record(plugin_id, plugin_dir, package_file, error, floor);
    } catch (const std::exception& e) {
        error = std::string("the installed package cannot be read: ") + e.what();
    } catch (...) {
        error = "the installed package cannot be read";
    }
    refuse_installed_package(plugin_dir, package_file, floor);
    return false;
}

void refuse_installed_package(const fs::path& plugin_dir, const fs::path& package_file, const PackageRecord* floor)
{
    // Nothing that could not be recorded as checked is left to load.
    boost::system::error_code ec;
    fs::remove(package_file, ec);
    std::string error;
    if (floor == nullptr || !write_package_record(plugin_dir, *floor, error))
        fs::remove(plugin_dir / PACKAGE_RECORD_FILE, ec);
}

bool check_wheel_import_name(const fs::path& wheel, const std::string& name, std::string& error)
{
    if (!is_safe_import_name(name)) {
        error = "Wheel entry package is not a plain Python module name: " + name;
        return false;
    }

    mz_zip_archive archive;
    mz_zip_zero_struct(&archive);
    if (!open_zip_reader(&archive, wheel.string())) {
        error = "Failed to open wheel as zip: " + wheel.string();
        return false;
    }
    std::vector<std::string> entries;
    const mz_uint            count = mz_zip_reader_get_num_files(&archive);
    for (mz_uint i = 0; i < count; ++i) {
        mz_zip_archive_file_stat stat;
        if (!mz_zip_reader_file_stat(&archive, i, &stat))
            continue;
        std::string entry = decode_archive_entry_path(&archive, stat);
        std::replace(entry.begin(), entry.end(), '\\', '/');
        entries.push_back(std::move(entry));
    }
    close_zip_reader(&archive);

    if (!has_top_level_entry(entries, name)) {
        error = "Wheel does not hold its entry package at its top: " + name;
        return false;
    }
    return true;
}

bool is_wheel_path(const std::string& path)
{
    std::string extension = fs::path(path).extension().string();
    std::transform(extension.begin(), extension.end(), extension.begin(),
                   [](char c) { return static_cast<char>(std::tolower(static_cast<unsigned char>(c))); });
    return extension == ".whl";
}

bool check_entry_package(const std::string& entry_path, const std::string& entry_package, std::string& error)
{
    return !is_wheel_path(entry_path) || check_wheel_import_name(fs::path(entry_path), entry_package, error);
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
