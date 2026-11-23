#include "PluginTrust.hpp"

#include <algorithm>
#include <cctype>
#include <cstddef>
#include <cstdint>
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

json read_trust_doc(const AppConfig& config)
{
    json doc = json::parse(config.get(PLUGIN_TRUST_KEY), nullptr, /*allow_exceptions=*/false);
    return doc.is_object() ? doc : json::object();
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

std::string to_lower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(),
                   [](char c) { return static_cast<char>(std::tolower(static_cast<unsigned char>(c))); });
    return value;
}

bool all_digits(const std::string& text)
{
    return !text.empty() && std::all_of(text.begin(), text.end(), [](char c) { return c >= '0' && c <= '9'; });
}

// host[:port] or [IPv6][:port] in its one spelling (see normalize_server_url()).
std::string normalize_authority(const std::string& authority, const std::string& scheme)
{
    // User info is refused by the cloud settings; such an address is left as it is.
    if (authority.find('@') != std::string::npos)
        return authority;
    const bool        ipv6     = !authority.empty() && authority.front() == '[';
    const std::size_t host_end = ipv6 ? authority.find(']') : std::string::npos;
    const std::size_t colon    = ipv6 ? (host_end == std::string::npos ? std::string::npos : authority.find(':', host_end))
                                      : authority.rfind(':');
    std::string       host     = to_lower(authority.substr(0, colon));
    std::string       port     = colon == std::string::npos ? std::string() : authority.substr(colon + 1);
    // A fully qualified name (example.org.) is the same host.
    while (!ipv6 && !host.empty() && host.back() == '.')
        host.pop_back();
    if (all_digits(port)) {
        port.erase(0, std::min(port.find_first_not_of('0'), port.size() - 1));
        if ((scheme == "https" && port == "443") || (scheme == "http" && port == "80"))
            port.clear();
    }
    // An empty port (host:) is the default one; any other port stays as written.
    return port.empty() ? host : host + ":" + port;
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
    const std::string text = trim_value(url);
    if (text.empty())
        return text;
    std::string       scheme = "https";
    std::size_t       start  = 0;
    const std::size_t marker = text.find("://");
    if (marker != std::string::npos) {
        scheme = to_lower(text.substr(0, marker));
        start  = marker + 3;
    }
    const std::size_t end    = text.find_first_of("/?#", start);
    std::string       result = scheme + "://" +
                         normalize_authority(text.substr(start, end == std::string::npos ? std::string::npos : end - start), scheme) +
                         (end == std::string::npos ? std::string() : text.substr(end));
    while (!result.empty() && result.back() == '/')
        result.pop_back();
    return result;
}

ServerPins server_pins(const AppConfig& config, const std::string& server_url)
{
    ServerPins pins;
    const json doc   = read_trust_doc(config);
    const auto entry = doc.find(normalize_server_url(server_url));
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
    std::string key;
    if (!trim_value(pins.public_key).empty() && public_key_id(pins.public_key, &key).empty())
        return false;
    json              doc = read_trust_doc(config);
    const std::string url = normalize_server_url(server_url);
    if (key.empty() && !pins.allow_unverified)
        doc.erase(url);
    else
        doc[url] = {{"public_key", key}, {"allow_unverified", pins.allow_unverified}};
    config.set(PLUGIN_TRUST_KEY, doc.dump());
    return true;
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
    ServerTrust       trust;
    const std::string url = normalize_server_url(server_url);
    // Without an address the agent talks to CosmoCloud (decision 0201).
    if (url.empty() || url == CLOUD_SERVER_URL) {
        trust.cosmyx_server = true;
        trust.keys          = built_in_keys();
        return trust;
    }
    const ServerPins pins = server_pins(config, url);
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
    {
        boost::nowide::ofstream file(temp.string(), std::ios::binary | std::ios::trunc);
        const std::string       text = record_to_json(record);
        file.write(text.data(), static_cast<std::streamsize>(text.size()));
        if (!file) {
            error = "cannot write " + temp.string();
            return false;
        }
    }
    boost::system::error_code ec;
    fs::rename(temp, target, ec);
    if (ec) {
        fs::remove(temp, ec);
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
bool commit_package_record(const std::string& plugin_id, const fs::path& plugin_dir, const fs::path& package_file, std::string& error)
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

    // Nothing that could not be recorded as checked is left to load.
    boost::system::error_code ec;
    fs::remove(plugin_dir / PACKAGE_RECORD_FILE, ec);
    fs::remove(package_file, ec);
    return false;
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

bool check_entry_package(const std::string& entry_path, const std::string& entry_package, std::string& error)
{
    std::string extension = fs::path(entry_path).extension().string();
    std::transform(extension.begin(), extension.end(), extension.begin(),
                   [](char c) { return static_cast<char>(std::tolower(static_cast<unsigned char>(c))); });
    return extension != ".whl" || check_wheel_import_name(fs::path(entry_path), entry_package, error);
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
