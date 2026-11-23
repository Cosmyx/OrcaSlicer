#ifndef slic3r_GUI_Cosmyx_logic_PluginSigning_hpp_
#define slic3r_GUI_Cosmyx_logic_PluginSigning_hpp_

// Verification of the Ed25519 signature that CosmoCloud puts on every plugin
// package row (CosmoCloud protocol "Plugin package signatures", decision 0204).
//
// verify_package_row() runs the ten steps of the protocol in their order and
// returns "ok" or the reason of the first failing step. The reasons are the
// protocol's stable strings; the test vectors of the server
// (tests/cosmyx/data/plugin-signatures.json) pin every one of them.
//
// The keys come from the build (PRODUCTION_KEYS) and, for a custom server,
// from the user's own pins (PluginTrust.hpp), never from a server response.
//
// wxWidgets-free and filesystem-free (OpenSSL and nlohmann::json only), so
// cosmyx_tests checks it directly.

#include <array>
#include <cstddef>
#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <vector>

#include <nlohmann/json.hpp>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// --- Reasons ----------------------------------------------------------------

// The protocol's results, in step order.
constexpr const char* SIGN_OK                = "ok";
constexpr const char* SIGN_MALFORMED_ROW     = "malformed_row";
constexpr const char* SIGN_WRONG_PLUGIN      = "wrong_plugin";
constexpr const char* SIGN_WRONG_VERSION     = "wrong_version";
constexpr const char* SIGN_WRONG_PLATFORM    = "wrong_platform";
constexpr const char* SIGN_MISSING_SIGNATURE = "missing_signature";
constexpr const char* SIGN_UNKNOWN_KEY       = "unknown_key";
constexpr const char* SIGN_BAD_SIGNATURE     = "bad_signature";
constexpr const char* SIGN_SIZE_MISMATCH     = "size_mismatch";
constexpr const char* SIGN_SHA256_MISMATCH   = "sha256_mismatch";
constexpr const char* SIGN_KIND_MISMATCH     = "kind_mismatch";
// The fork's own reasons, outside the server vectors (decision 0204).
constexpr const char* SIGN_DOWNGRADE         = "downgrade";     // older than the recorded installed version
constexpr const char* SIGN_NO_PINNED_KEY     = "no_pinned_key"; // nothing to verify against for this server
constexpr const char* SIGN_NO_ROW            = "no_row";        // the download row did not reach the check
constexpr const char* SIGN_UNKNOWN_SLOT      = "unknown_slot";  // this build cannot name its os/arch

// --- Pinned keys ------------------------------------------------------------

struct PinnedKey
{
    const char* key_id;     // 64 lowercase hex: SHA-256 of the raw public key
    const char* public_key; // 64 lowercase hex: the raw 32-byte Ed25519 public key
};

// The CosmoCloud production signing keys, copied from `just plugin-keys` on the
// production server (never from a runtime fetch). EMPTY ON PURPOSE: the
// production key is not known yet (decision 0204, same pattern as 0202). While
// it is empty, every plugin install or update from the Cosmyx server is
// refused with SIGN_NO_PINNED_KEY.
// TODO(release): add {key_id, public_key} from `just plugin-keys`; the test
// "pinned production keys hash to their key id" checks each entry.
constexpr std::array<PinnedKey, 0> PRODUCTION_KEYS{};

// Key ids that are never trusted again, even when pinned (rotation after a leak).
constexpr std::array<const char*, 0> REVOKED_KEY_IDS{};

// key_id -> raw 32-byte public key.
using KeyTable = std::map<std::string, std::string>;
using KeyIdSet = std::set<std::string>;

// Lowercase hex of bytes, and its inverse (lowercase only; false otherwise).
std::string to_hex(const std::string& bytes);
bool        from_lower_hex(const std::string& hex, std::string& bytes);
bool        is_lower_hex(const std::string& text, std::size_t length);

// Raw SHA-256 of data (32 bytes), and its lowercase hex.
std::string sha256_raw(const std::string& data);
std::string sha256_hex(const std::string& data);

// The key id of a raw 32-byte public key: lowercase hex of its SHA-256.
std::string key_id_of(const std::string& raw_public_key);

// Adds a pin given as hex. Refuses (false, error set) a public key that is not
// 64 lowercase hex, and a key id that is not the hash of that key.
bool add_pinned_key(KeyTable& table, const std::string& key_id, const std::string& public_key_hex, std::string& error);

// PRODUCTION_KEYS as a table, and REVOKED_KEY_IDS as a set.
KeyTable built_in_keys();
KeyIdSet revoked_key_ids();

// --- Row checks -------------------------------------------------------------

// What the client asked for. version empty means "none" (latest). os is one of
// win, macosx, linux and arch one of arm64, x86_64, i386, never "*".
struct ClientRequest
{
    std::string plugin_id;
    std::string version;
    std::string os;
    std::string arch;
};

// The protocol's vocabulary for this client: "macos" (platform_os_type())
// becomes "macosx". False when the slot cannot be named, which means the
// build cannot verify at all (SIGN_UNKNOWN_SLOT).
bool client_slot(const std::string& platform_os, const std::string& platform_arch, std::string& os, std::string& arch);

// Field rules of step 1.
bool is_plugin_id(const std::string& text); // lowercase uuid4
bool is_strict_version(const std::string& text); // X.Y.Z, no leading zero, parts of 1 to 6 digits

// The signed message of a row (whose fields passed step 1) for a key id.
std::string signed_message(const nlohmann::json& row, const std::string& key_id);

// One-shot Ed25519 verification (RFC 8032, pure): raw 32-byte key, raw 64-byte
// signature. The algorithm is fixed here, never taken from the server.
bool ed25519_verify(const std::string& raw_public_key, const std::string& message, const std::string& raw_signature);

// Steps 1 to 10. On "ok", *key_id (when given) gets the key id that verified.
std::string verify_package_row(const nlohmann::json&  row,
                               const std::string&     body,
                               const ClientRequest&   request,
                               const KeyTable&        pinned,
                               const KeyIdSet&        revoked,
                               std::string*           key_id = nullptr);

// Steps 1 to 4 and 8 to 10, without the signature steps: the check of a server
// the user allowed to serve unverified plugins (decision 0204).
std::string check_unsigned_package_row(const nlohmann::json& row, const std::string& body, const ClientRequest& request);

// --- Anti-rollback ----------------------------------------------------------

// True when both are strict versions and candidate is lower than installed.
bool is_downgrade(const std::string& installed, const std::string& candidate);

// --- Entry package name (CosmoCloud decision 0077, an upstream bug) ----------

// An ASCII Python identifier, not a dunder name, not a Windows device name.
bool is_safe_import_name(const std::string& name);

// The wheel entries (archive names, '/' separated) hold name at their top, as
// a package folder (name/...) or a module (name.py), matched exactly.
bool has_top_level_entry(const std::vector<std::string>& entries, const std::string& name);

// --- Package record -----------------------------------------------------------

// Written as .cosmyx_package.json in the plugin folder after a package passed
// the check. key_id is empty for a package from a server the user allowed to
// serve unverified plugins.
constexpr const char* PACKAGE_RECORD_FILE = ".cosmyx_package.json";

struct PackageRecord
{
    std::string   plugin_id;
    std::string   version;
    std::string   sha256;
    std::uint64_t size = 0;
    std::string   key_id;

    bool verified() const { return !key_id.empty(); }
};

std::string record_to_json(const PackageRecord& record);
// False for anything that is not a record this code wrote.
bool record_from_json(const std::string& text, PackageRecord& record);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_logic_PluginSigning_hpp_
