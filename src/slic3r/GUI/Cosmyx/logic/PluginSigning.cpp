#include "PluginSigning.hpp"

#include <algorithm>
#include <array>
#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <nlohmann/json.hpp>
#include <openssl/crypto.h>
#include <openssl/evp.h>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

using nlohmann::json;

// "cosmocloud-plugin-package-v1" and its trailing NUL: 29 bytes.
const std::string SIGNED_DOMAIN("cosmocloud-plugin-package-v1\0", 29);

constexpr std::uint64_t MAX_SIZE = (std::uint64_t(1) << 53) - 1;

constexpr const char* HEX_DIGITS = "0123456789abcdef";

const std::array<const char*, 4> TARGET_OSES   = {"*", "win", "macosx", "linux"};
const std::array<const char*, 4> TARGET_ARCHES = {"*", "arm64", "x86_64", "i386"};

const unsigned char ZIP_MAGIC[4] = {0x50, 0x4b, 0x03, 0x04};

bool is_digit(char c) { return c >= '0' && c <= '9'; }

int hex_value(char c)
{
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c >= 'a' && c <= 'f')
        return c - 'a' + 10;
    return -1;
}

std::vector<std::string> split(const std::string& text, char separator)
{
    std::vector<std::string> parts;
    std::size_t              start = 0;
    while (true) {
        const std::size_t end = text.find(separator, start);
        parts.push_back(text.substr(start, end == std::string::npos ? std::string::npos : end - start));
        if (end == std::string::npos)
            return parts;
        start = end + 1;
    }
}

template<std::size_t N> bool in_list(const std::string& value, const std::array<const char*, N>& list)
{
    return std::any_of(list.begin(), list.end(), [&value](const char* item) { return value == item; });
}

// The string value of key in object, or nullptr when absent or not a string.
const std::string* string_field(const json& object, const char* key)
{
    const auto it = object.find(key);
    if (it == object.end() || !it->is_string())
        return nullptr;
    return &it->get_ref<const std::string&>();
}

bool size_field(const json& object, std::uint64_t& size)
{
    const auto it = object.find("size");
    // is_number_integer() is false for 5.0, true, false and strings; a number
    // above the uint64 range is parsed as a float and refused too.
    if (it == object.end() || !it->is_number_integer())
        return false;
    if (it->is_number_unsigned())
        size = it->get<std::uint64_t>();
    else {
        const std::int64_t value = it->get<std::int64_t>();
        if (value < 1)
            return false;
        size = static_cast<std::uint64_t>(value);
    }
    return size >= 1 && size <= MAX_SIZE;
}

// The (os, arch) slots of a canonical targets string; false when it is not
// canonical. Every element is checked against the ASCII vocabulary before the
// elements are compared, so the comparison only ever sees known ASCII text.
bool target_set(const std::string& targets, std::vector<std::pair<std::string, std::string>>& slots)
{
    if (targets.empty())
        return false;
    const std::vector<std::string> elements = split(targets, ',');
    for (const std::string& element : elements) {
        const std::vector<std::string> parts = split(element, '/');
        if (parts.size() != 2 || !in_list(parts[0], TARGET_OSES) || !in_list(parts[1], TARGET_ARCHES))
            return false;
        if (parts[0] == "*" && parts[1] != "*")
            return false;
        slots.emplace_back(parts[0], parts[1]);
    }
    for (std::size_t i = 1; i < elements.size(); ++i)
        if (!(elements[i - 1] < elements[i]))
            return false;
    return true;
}

bool covers(const std::vector<std::pair<std::string, std::string>>& slots, const std::string& os, const std::string& arch)
{
    return std::any_of(slots.begin(), slots.end(), [&](const std::pair<std::string, std::string>& slot) {
        return (slot.first == os && (slot.second == arch || slot.second == "*")) || (slot.first == "*" && slot.second == "*");
    });
}

void append_u32be(std::string& out, std::uint32_t value)
{
    for (int shift = 24; shift >= 0; shift -= 8)
        out.push_back(static_cast<char>((value >> shift) & 0xff));
}

void append_u64be(std::string& out, std::uint64_t value)
{
    for (int shift = 56; shift >= 0; shift -= 8)
        out.push_back(static_cast<char>((value >> shift) & 0xff));
}

void append_lp(std::string& out, const std::string& text)
{
    append_u32be(out, static_cast<std::uint32_t>(text.size()));
    out += text;
}

bool equal_constant_time(const std::string& a, const std::string& b)
{
    return a.size() == b.size() && CRYPTO_memcmp(a.data(), b.data(), a.size()) == 0;
}

// Steps 1 to 4. Empty when they pass, else the reason.
std::string check_row_fields(const json& row, const ClientRequest& request)
{
    if (!row.is_object())
        return SIGN_MALFORMED_ROW;

    const std::string* plugin_id = string_field(row, "plugin_id");
    const std::string* version   = string_field(row, "version");
    const std::string* sha256    = string_field(row, "sha256");
    const std::string* kind      = string_field(row, "kind");
    const std::string* targets   = string_field(row, "targets");
    std::uint64_t      size      = 0;
    std::vector<std::pair<std::string, std::string>> slots;

    const auto signatures = row.find("signatures");
    if (plugin_id == nullptr || !is_plugin_id(*plugin_id) || version == nullptr || !is_strict_version(*version) ||
        sha256 == nullptr || !is_lower_hex(*sha256, 64) || !size_field(row, size) || kind == nullptr ||
        (*kind != "wheel" && *kind != "script") || targets == nullptr || !target_set(*targets, slots) ||
        (signatures != row.end() && !signatures->is_array()))
        return SIGN_MALFORMED_ROW;

    if (*plugin_id != request.plugin_id)
        return SIGN_WRONG_PLUGIN;
    if (!request.version.empty() && *version != request.version)
        return SIGN_WRONG_VERSION;
    if (!covers(slots, request.os, request.arch))
        return SIGN_WRONG_PLATFORM;
    return {};
}

// Steps 8 to 10, on a row whose fields passed step 1.
std::string check_body(const json& row, const std::string& body)
{
    std::uint64_t size = 0;
    size_field(row, size);
    if (static_cast<std::uint64_t>(body.size()) != size)
        return SIGN_SIZE_MISMATCH;

    std::string expected;
    from_lower_hex(row.at("sha256").get_ref<const std::string&>(), expected);
    if (!equal_constant_time(sha256_raw(body), expected))
        return SIGN_SHA256_MISMATCH;

    const bool is_zip = body.size() >= 4 && std::equal(ZIP_MAGIC, ZIP_MAGIC + 4, body.begin(), [](unsigned char m, char c) {
                            return m == static_cast<unsigned char>(c);
                        });
    if (is_zip != (row.at("kind").get_ref<const std::string&>() == "wheel"))
        return SIGN_KIND_MISMATCH;
    return SIGN_OK;
}

bool is_strict_version_parts(const std::string& text, std::array<std::uint32_t, 3>& parts)
{
    const std::vector<std::string> pieces = split(text, '.');
    if (pieces.size() != 3)
        return false;
    for (std::size_t i = 0; i < 3; ++i) {
        const std::string& piece = pieces[i];
        if (piece.empty() || piece.size() > 6 || !std::all_of(piece.begin(), piece.end(), is_digit))
            return false;
        if (piece.size() > 1 && piece[0] == '0')
            return false;
        parts[i] = static_cast<std::uint32_t>(std::stoul(piece));
    }
    return true;
}

} // namespace

// --- Hex and hashes -----------------------------------------------------------

std::string to_hex(const std::string& bytes)
{
    std::string out;
    out.reserve(bytes.size() * 2);
    for (char c : bytes) {
        const auto u = static_cast<unsigned char>(c);
        out.push_back(HEX_DIGITS[u >> 4]);
        out.push_back(HEX_DIGITS[u & 0x0f]);
    }
    return out;
}

bool is_lower_hex(const std::string& text, std::size_t length)
{
    return text.size() == length && std::all_of(text.begin(), text.end(), [](char c) { return hex_value(c) >= 0; });
}

bool from_lower_hex(const std::string& hex, std::string& bytes)
{
    bytes.clear();
    if (hex.size() % 2 != 0 || !is_lower_hex(hex, hex.size()))
        return false;
    bytes.reserve(hex.size() / 2);
    for (std::size_t i = 0; i < hex.size(); i += 2)
        bytes.push_back(static_cast<char>(hex_value(hex[i]) * 16 + hex_value(hex[i + 1])));
    return true;
}

std::string sha256_raw(const std::string& data)
{
    unsigned char digest[EVP_MAX_MD_SIZE];
    unsigned int  length = 0;
    if (EVP_Digest(data.data(), data.size(), digest, &length, EVP_sha256(), nullptr) != 1 || length != 32)
        return {};
    return std::string(reinterpret_cast<const char*>(digest), length);
}

std::string sha256_hex(const std::string& data) { return to_hex(sha256_raw(data)); }

std::string key_id_of(const std::string& raw_public_key) { return sha256_hex(raw_public_key); }

// --- Keys ---------------------------------------------------------------------

bool add_pinned_key(KeyTable& table, const std::string& key_id, const std::string& public_key_hex, std::string& error)
{
    std::string raw;
    if (!is_lower_hex(public_key_hex, 64) || !from_lower_hex(public_key_hex, raw)) {
        error = "public key is not 64 lowercase hex characters";
        return false;
    }
    if (key_id_of(raw) != key_id) {
        error = "key id " + key_id + " is not the SHA-256 of its public key";
        return false;
    }
    table[key_id] = raw;
    return true;
}

KeyTable built_in_keys()
{
    KeyTable table;
    for (const PinnedKey& pin : PRODUCTION_KEYS) {
        std::string error;
        // A bad entry is a build bug, caught by the cosmyx_tests check of
        // PRODUCTION_KEYS; skipping it here refuses its packages.
        add_pinned_key(table, pin.key_id, pin.public_key, error);
    }
    return table;
}

KeyIdSet revoked_key_ids() { return KeyIdSet(REVOKED_KEY_IDS.begin(), REVOKED_KEY_IDS.end()); }

// --- Row checks ---------------------------------------------------------------

bool client_slot(const std::string& platform_os, const std::string& platform_arch, std::string& os, std::string& arch)
{
    os   = platform_os == "macos" ? std::string("macosx") : platform_os;
    arch = platform_arch;
    return (os == "win" || os == "macosx" || os == "linux") && (arch == "arm64" || arch == "x86_64" || arch == "i386");
}

bool is_plugin_id(const std::string& text)
{
    if (text.size() != 36)
        return false;
    const std::vector<std::string> groups = split(text, '-');
    if (groups.size() != 5)
        return false;
    const std::array<std::size_t, 5> lengths = {8, 4, 4, 4, 12};
    for (std::size_t i = 0; i < 5; ++i)
        if (!is_lower_hex(groups[i], lengths[i]))
            return false;
    return groups[2][0] == '4' && std::string("89ab").find(groups[3][0]) != std::string::npos;
}

bool is_strict_version(const std::string& text)
{
    std::array<std::uint32_t, 3> parts{};
    return is_strict_version_parts(text, parts);
}

std::string signed_message(const json& row, const std::string& key_id)
{
    std::string sha256;
    from_lower_hex(row.at("sha256").get_ref<const std::string&>(), sha256);
    std::uint64_t size = 0;
    size_field(row, size);

    std::string message = SIGNED_DOMAIN;
    append_lp(message, key_id);
    append_lp(message, row.at("plugin_id").get_ref<const std::string&>());
    append_lp(message, row.at("version").get_ref<const std::string&>());
    append_lp(message, row.at("kind").get_ref<const std::string&>());
    append_lp(message, row.at("targets").get_ref<const std::string&>());
    message += sha256;
    append_u64be(message, size);
    return message;
}

bool ed25519_verify(const std::string& raw_public_key, const std::string& message, const std::string& raw_signature)
{
    if (raw_public_key.size() != 32 || raw_signature.size() != 64)
        return false;

    std::unique_ptr<EVP_PKEY, decltype(&EVP_PKEY_free)> key(
        EVP_PKEY_new_raw_public_key(EVP_PKEY_ED25519, nullptr, reinterpret_cast<const unsigned char*>(raw_public_key.data()),
                                    raw_public_key.size()),
        &EVP_PKEY_free);
    if (!key)
        return false;
    std::unique_ptr<EVP_MD_CTX, decltype(&EVP_MD_CTX_free)> context(EVP_MD_CTX_new(), &EVP_MD_CTX_free);
    if (!context)
        return false;
    // Ed25519 takes no digest: NULL md, then one-shot over the whole message.
    if (EVP_DigestVerifyInit(context.get(), nullptr, nullptr, nullptr, key.get()) != 1)
        return false;
    return EVP_DigestVerify(context.get(), reinterpret_cast<const unsigned char*>(raw_signature.data()), raw_signature.size(),
                            reinterpret_cast<const unsigned char*>(message.data()), message.size()) == 1;
}

std::string verify_package_row(const json&         row,
                               const std::string&  body,
                               const ClientRequest& request,
                               const KeyTable&     pinned,
                               const KeyIdSet&     revoked,
                               std::string*        key_id)
{
    // 1-4.
    const std::string field_error = check_row_fields(row, request);
    if (!field_error.empty())
        return field_error;

    // 5. The v1 Ed25519 entries; every other entry is skipped.
    std::vector<const json*> entries;
    const auto signatures = row.find("signatures");
    if (signatures != row.end()) {
        for (const json& entry : *signatures) {
            if (!entry.is_object())
                continue;
            const std::string* format = string_field(entry, "format");
            const std::string* alg    = string_field(entry, "alg");
            if (format != nullptr && *format == "v1" && alg != nullptr && *alg == "ed25519")
                entries.push_back(&entry);
        }
    }
    if (entries.empty())
        return SIGN_MISSING_SIGNATURE;

    // 6. Under a pinned key that is not revoked.
    std::vector<const json*> candidates;
    for (const json* entry : entries) {
        const std::string* id = string_field(*entry, "key_id");
        if (id != nullptr && pinned.count(*id) != 0 && revoked.count(*id) == 0)
            candidates.push_back(entry);
    }
    if (candidates.empty())
        return SIGN_UNKNOWN_KEY;

    // 7. Any candidate verifies, in array order.
    const std::string* verified_id = nullptr;
    for (const json* entry : candidates) {
        const std::string* sig = string_field(*entry, "sig");
        std::string        raw_signature;
        if (sig == nullptr || !is_lower_hex(*sig, 128) || !from_lower_hex(*sig, raw_signature))
            continue;
        const std::string& id = entry->at("key_id").get_ref<const std::string&>();
        if (ed25519_verify(pinned.at(id), signed_message(row, id), raw_signature)) {
            verified_id = &id;
            break;
        }
    }
    if (verified_id == nullptr)
        return SIGN_BAD_SIGNATURE;

    // 8-10.
    const std::string result = check_body(row, body);
    if (result == SIGN_OK && key_id != nullptr)
        *key_id = *verified_id;
    return result;
}

std::string check_unsigned_package_row(const json& row, const std::string& body, const ClientRequest& request)
{
    const std::string field_error = check_row_fields(row, request);
    return field_error.empty() ? check_body(row, body) : field_error;
}

// --- Anti-rollback --------------------------------------------------------------

bool is_downgrade(const std::string& installed, const std::string& candidate)
{
    std::array<std::uint32_t, 3> from{}, to{};
    return is_strict_version_parts(installed, from) && is_strict_version_parts(candidate, to) && to < from;
}

// --- Entry package name ---------------------------------------------------------

bool is_safe_import_name(const std::string& name)
{
    // 255 bytes: the longest file name ext4, APFS and NTFS all take.
    if (name.empty() || name.size() > 255)
        return false;
    const auto is_start = [](char c) { return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_'; };
    if (!is_start(name[0]) || !std::all_of(name.begin(), name.end(), [&](char c) { return is_start(c) || is_digit(c); }))
        return false;
    if (name.size() >= 4 && name.compare(0, 2, "__") == 0 && name.compare(name.size() - 2, 2, "__") == 0)
        return false;

    std::string upper = name;
    for (char& c : upper)
        if (c >= 'a' && c <= 'z')
            c = static_cast<char>(c - 'a' + 'A');
    if (upper == "CON" || upper == "PRN" || upper == "AUX" || upper == "NUL")
        return false;
    if (upper.size() == 4 && (upper.compare(0, 3, "COM") == 0 || upper.compare(0, 3, "LPT") == 0) && is_digit(upper[3]))
        return false;
    return true;
}

bool has_top_level_entry(const std::vector<std::string>& entries, const std::string& name)
{
    const std::string folder = name + "/";
    const std::string module = name + ".py";
    return std::any_of(entries.begin(), entries.end(), [&](const std::string& entry) {
        return entry == module || (entry.size() > folder.size() && entry.compare(0, folder.size(), folder) == 0);
    });
}

// --- Package record -------------------------------------------------------------

std::string record_to_json(const PackageRecord& record)
{
    json doc = json::object();
    doc["plugin_id"] = record.plugin_id;
    doc["version"]   = record.version;
    doc["sha256"]    = record.sha256;
    doc["size"]      = record.size;
    doc["key_id"]    = record.key_id;
    return doc.dump(2) + "\n";
}

bool record_from_json(const std::string& text, PackageRecord& record)
{
    const json doc = json::parse(text, nullptr, /*allow_exceptions=*/false);
    if (!doc.is_object())
        return false;
    const std::string* plugin_id = string_field(doc, "plugin_id");
    const std::string* version   = string_field(doc, "version");
    const std::string* sha256    = string_field(doc, "sha256");
    const std::string* key_id    = string_field(doc, "key_id");
    std::uint64_t      size      = 0;
    if (plugin_id == nullptr || !is_plugin_id(*plugin_id) || version == nullptr || !is_strict_version(*version) ||
        sha256 == nullptr || !is_lower_hex(*sha256, 64) || !size_field(doc, size) || key_id == nullptr ||
        (!key_id->empty() && !is_lower_hex(*key_id, 64)))
        return false;
    record = {*plugin_id, *version, *sha256, size, *key_id};
    return true;
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
