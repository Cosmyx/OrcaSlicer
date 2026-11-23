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
// - after the install, .cosmyx_package.json records what was installed, and a
//   stale wheel extraction is removed so the next load extracts that package.
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

// Folder of the extracted wheels, inside a plugin folder (upstream name).
constexpr const char* WHEEL_EXTRACT_DIR = "__whl_extracted__";

// Address with surrounding spaces and trailing slashes removed.
std::string normalize_server_url(const std::string& url);

// The user's settings for one custom server.
struct ServerPins
{
    std::string public_key; // 64 lowercase hex, or empty
    bool        allow_unverified = false;
};

ServerPins server_pins(const AppConfig& config, const std::string& server_url);
// Stores the settings of server_url; empty settings remove its entry.
void set_server_pins(AppConfig& config, const std::string& server_url, const ServerPins& pins);

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

// Keeps the record of a package that passed check_plugin_package(), until its
// install commits it. Thread-safe.
void remember_checked_package(const PackageRecord& record);

// After plugin_id was installed in plugin_dir from package_file: finds the
// remembered record of those exact bytes (by SHA-256), removes a stale wheel
// extraction and writes the record. With no remembered record (a local
// install), any record left in plugin_dir is removed, so the plugin reads as
// unverified. False only when a write fails.
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
