#ifndef slic3r_GUI_Cosmyx_logic_PluginTrust_hpp_
#define slic3r_GUI_Cosmyx_logic_PluginTrust_hpp_

// What a downloaded plugin package is checked against, and what is kept once
// it passed (decision 0204):
//
// - the Cosmyx server (CLOUD_SERVER_URL) is checked against the keys pinned in
//   the build, and only those;
// - another server is checked against the public key the user pinned for its
//   address in Preferences; with none, the package is refused, unless the user
//   allowed unverified plugins from that server, which still checks the row,
//   the size, the SHA-256 and the kind;
// - a version lower than the one recorded as installed is refused (downgrade);
// - after the install, .cosmyx_package.json records what was installed; bytes
//   other than the ones that passed are removed and the install refused.
//
// wxWidgets-free, so cosmyx_tests checks it directly.

#include <string>

#include <boost/filesystem/path.hpp>
#include <nlohmann/json.hpp>

#include "PluginSigning.hpp"

namespace Slic3r {

class AppConfig;

namespace GUI {
namespace Cosmyx {

// App key holding the user's pins, as JSON:
// {"<server address>": {"public_key": "<64 hex>", "allow_unverified": false}}
constexpr const char* PLUGIN_TRUST_KEY = "cosmyx_plugin_trust";

// One spelling per server address, so a pin is found whatever the user typed
// and the Cosmyx address is always recognised: spaces trimmed, scheme and host
// in lower case (https when none is given), trailing dots of the host, the
// default port (443 for https, 80 for http), leading zeros of the port and
// trailing slashes removed. The path keeps its case. Empty stays empty.
std::string normalize_server_url(const std::string& url);

// The user's settings for one custom server.
struct ServerPins
{
    std::string public_key; // 64 lowercase hex, or empty
    bool        allow_unverified = false;
};

// A stored key is read in any case and with surrounding spaces. A stored key
// that is not a key (hand-edited, truncated) gives no key and no opt-in, so
// that server is refused: a pin never falls back to unverified plugins.
ServerPins server_pins(const AppConfig& config, const std::string& server_url);
// Stores the settings of server_url, the key as 64 lowercase hex; empty
// settings remove its entry. False, and nothing stored, when public_key is
// neither empty nor a key (see public_key_id()).
bool set_server_pins(AppConfig& config, const std::string& server_url, const ServerPins& pins);

// The key id of a public key typed by the user (spaces trimmed, any case), or
// empty when it is not 64 hex characters. *normalized gets the lowercase hex.
std::string public_key_id(const std::string& typed, std::string* normalized = nullptr);

// What packages from one server are checked against.
struct ServerTrust
{
    bool     cosmyx_server    = false;
    KeyTable keys;
    bool     allow_unverified = false; // only ever true for a custom server with no key
};

ServerTrust server_trust(const AppConfig& config, const std::string& server_url);

// The result of the whole check of one download.
struct PackageVerdict
{
    std::string   reason; // SIGN_OK or a reason
    PackageRecord record; // filled on SIGN_OK; key_id empty when unverified
    bool ok() const { return reason == SIGN_OK; }
    bool verified() const { return ok() && record.verified(); }
};

// The version a download request carries: empty (the latest) or a strict
// X.Y.Z. False for any other requested version, which is refused with
// SIGN_WRONG_VERSION rather than sent as a request for the latest.
bool request_version(const std::string& requested, std::string& version);

// row may be null (the row did not reach the check: SIGN_NO_ROW).
// installed_version is the version recorded for the installed package, or
// empty. allow_downgrade is true only when the user chose a downgrade.
PackageVerdict check_plugin_package(const nlohmann::json* row,
                                    const std::string&    body,
                                    const ClientRequest&  request,
                                    const ServerTrust&    trust,
                                    const KeyIdSet&       revoked,
                                    const std::string&    installed_version,
                                    bool                  allow_downgrade);

// --- Record -------------------------------------------------------------------

bool read_package_record(const boost::filesystem::path& plugin_dir, PackageRecord& record);
bool write_package_record(const boost::filesystem::path& plugin_dir, const PackageRecord& record, std::string& error);

// Keeps the record of a package that passed check_plugin_package(), keyed by
// its plugin id and SHA-256, until its install commits it. Thread-safe.
void remember_checked_package(const PackageRecord& record);

// Drops every record of plugin_id that no install committed: called when an
// install ends, failed or not. Thread-safe.
void forget_checked_packages(const std::string& plugin_id);

// After plugin_id was installed in plugin_dir from package_file (a cloud
// install, so its bytes passed the check): takes the remembered record of
// plugin_id for those exact bytes (SHA-256 and size) and writes it. With no
// such record the installed bytes are not the ones checked (the downloaded
// file was swapped before the install copied it). That case and a record that
// cannot be written return false with error set, and remove package_file and
// any record in plugin_dir, so nothing that is not recorded as checked loads.
bool commit_package_record(const std::string&             plugin_id,
                           const boost::filesystem::path& plugin_dir,
                           const boost::filesystem::path& package_file,
                           std::string&                   error);

// --- Wheel entry package ------------------------------------------------------

// The entry package of a wheel is safe to extract to and import: a plain
// module name (is_safe_import_name) that the wheel holds at its top, as a
// package folder or a module. Error messages are English, like the upstream
// wheel checks they join.
bool check_wheel_import_name(const boost::filesystem::path& wheel, const std::string& name, std::string& error);

// The same check right before a plugin is imported, since the catalog may set
// the entry package of a cloud plugin: applied when entry_path is a wheel
// (any case of .whl), true for any other entry.
bool check_entry_package(const std::string& entry_path, const std::string& entry_package, std::string& error);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_logic_PluginTrust_hpp_
