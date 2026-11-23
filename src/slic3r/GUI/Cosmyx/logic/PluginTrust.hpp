#ifndef slic3r_GUI_Cosmyx_logic_PluginTrust_hpp_
#define slic3r_GUI_Cosmyx_logic_PluginTrust_hpp_

// What a downloaded plugin package is checked against, and what is kept once
// it passed (decision 0204):
//
// - an address that is not plainly scheme://host[:port][/path] (see
//   parse_server_address()) is unrecognised: its packages are refused, and
//   neither the build's keys nor any pin or opt-in of the user apply to it;
// - the Cosmyx server (the host of CLOUD_SERVER_URL, over https on its
//   default port, any path) is checked against the keys pinned in the build,
//   and only those; any other scheme or port on that host is unrecognised;
// - another server is checked against the public key the user pinned for its
//   address in Preferences; with none, the package is refused, unless the user
//   allowed unverified plugins from that server, which still checks the row,
//   the size, the SHA-256 and the kind;
// - a version lower than the one recorded as installed is refused (downgrade);
// - after the install, .cosmyx_package.json records what was installed; bytes
//   other than the ones that passed are removed and the install refused.
//
// wxWidgets-free, so cosmyx_tests checks it directly.

#include <functional>
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

// Client-side refusal reason: the address is unrecognised (decision 0204).
constexpr const char* SIGN_UNRECOGNISED_SERVER = "unrecognised_server";
// Client-side refusal reason: the app closed before the download could be
// checked against its settings (package_gate(), decision 0204).
constexpr const char* SIGN_APP_GONE = "app_gone";

// One spelling per server address, so a pin is found whatever the user typed:
// parse_server_address() then ServerAddress::url(), so scheme and host in
// lower case, the trailing dot of the host, the default port (443 for https,
// 80 for http), leading zeros of the port and trailing slashes removed; the
// path keeps its case. Empty for an empty or unrecognised address.
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
// neither empty nor a key (see public_key_id()), server_url is unrecognised,
// or the stored document cannot be read (saving over it would drop the pins
// of every other server). An unrecognised address has no pins.
bool set_server_pins(AppConfig& config, const std::string& server_url, const ServerPins& pins);

// What Apply in Preferences does with the plugin rows, which show the pins of
// the API address they were loaded for (loaded_url), once the API address
// applied_url is accepted.
enum class PinsSave {
    Typed, // the same server, whatever its spelling: store what the rows hold for it
    Keep,  // another server: store nothing, so its own pins stay, and show them
    None,  // the Cosmyx server or an unrecognised address: store nothing, never used
};
PinsSave pins_to_save(const std::string& loaded_url, const std::string& applied_url);

// The key id of a public key typed by the user (spaces trimmed, any case), or
// empty when it is not 64 hex characters. *normalized gets the lowercase hex.
std::string public_key_id(const std::string& typed, std::string* normalized = nullptr);

// What packages from one server are checked against.
struct ServerTrust
{
    bool     cosmyx_server    = false;
    KeyTable keys;
    bool     allow_unverified = false; // only ever true for a custom server with no key
    bool     unrecognised     = false; // packages refused with SIGN_UNRECOGNISED_SERVER
};

ServerTrust server_trust(const AppConfig& config, const std::string& server_url);

// --- Without the app ------------------------------------------------------------

// How the cloud installs of this process are checked (decision 0204, "Without
// the app").
enum class PackageGate
{
    // No OrcaSlicer app was ever seen in this process: the upstream plugin
    // tests drive the plugin manager headless, with fake servers over plain
    // http and packages that carry no signature. There are no trust settings
    // to read, so both hooks behave as upstream (the download is logged as
    // not checked).
    Unchecked,
    // The app runs: the download is checked against its trust settings.
    Checked,
    // The app was seen but is gone (shutdown, while a detached install
    // worker still runs): its settings cannot be read, so the download is
    // refused. A commit still matches the installed bytes against the checked
    // record, which needs no setting.
    AppGone,
};

// The gate for a hook running now. app_running_now is whether the OrcaSlicer
// app runs at this moment. Once it was true, the check stays on for the rest
// of the process: a process-wide latch, set here or by note_app_seen(), never
// cleared outside tests. Thread-safe.
PackageGate package_gate(bool app_running_now);

// Sets the latch: called as soon as the app is created, before any install
// can start, so a download that ends after the app is gone is never let
// through. Thread-safe.
void note_app_seen();

// Clears the latch. For tests only: the app process never calls it.
void reset_package_gate_for_tests();

// What one cloud download is checked against.
struct DownloadCheck
{
    std::string server; // the API address the agent uses
    ServerTrust trust;
};

// config is the app config, or null before it is loaded: the Cosmyx server is
// then assumed, with the build's keys only, so a missing config never relaxes
// the check.
DownloadCheck download_check(const AppConfig* config);

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

// What the download hook is given, all of it read outside the app config.
struct DownloadInput
{
    std::string           plugin_id;
    std::string           requested_version; // as the installer asked: empty (latest) or X.Y.Z
    const nlohmann::json* row = nullptr;     // the row as served, or null
    std::string           body;
    std::string           installed_version; // from the installed package's record, or empty
    std::string           platform_os;       // platform_os_type()
    std::string           platform_arch;     // platform_architecture()
    KeyIdSet              revoked;
};

// The decision of the download hook.
struct DownloadDecision
{
    PackageGate    gate = PackageGate::Unchecked;
    DownloadCheck  check;   // filled when gate is Checked
    PackageVerdict verdict; // SIGN_APP_GONE when gate is AppGone
    // The body may be installed: unchecked (no app ever seen) or passed.
    bool install() const { return gate == PackageGate::Unchecked || verdict.ok(); }
};

// The whole download hook, wx-free: the gate (package_gate()), then, with the
// check on, the requested version, the client slot and check_plugin_package().
// A package that passed is remembered (remember_checked_package()) for its
// commit. config is read only when the gate is Checked (see download_check()).
DownloadDecision decide_download(bool app_running_now, const AppConfig* config, const DownloadInput& input);

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
// cannot be written return false with error set, and refuse the install
// (refuse_installed_package()), so nothing that is not recorded as checked
// loads. floor is the record of the package this install replaces, if any.
bool commit_package_record(const std::string&             plugin_id,
                           const boost::filesystem::path& plugin_dir,
                           const boost::filesystem::path& package_file,
                           std::string&                   error,
                           const PackageRecord*           floor = nullptr);

// The commit of a cloud install: metadata_matches (which reads the installed
// package again, and may throw) and then commit_package_record(). A false or a
// throw from metadata_matches refuses the install (refuse_installed_package()
// with floor) and returns false with error set.
bool commit_checked_install(const std::string&                       plugin_id,
                            const boost::filesystem::path&           plugin_dir,
                            const boost::filesystem::path&           package_file,
                            const std::function<bool(std::string&)>& metadata_matches,
                            std::string&                             error,
                            const PackageRecord*                     floor = nullptr);

// The whole commit hook, wx-free. With the gate Unchecked (no app ever seen)
// the install goes on as upstream: no record, nothing refused. Otherwise, the
// app running or gone, commit_checked_install(): the installed bytes must be
// the ones a check passed, so a download checked while the app ran and
// committed after it closed still gets its record, and bytes never checked
// are refused.
bool commit_cloud_install(bool                                     app_running_now,
                          const std::string&                       plugin_id,
                          const boost::filesystem::path&           plugin_dir,
                          const boost::filesystem::path&           package_file,
                          const std::function<bool(std::string&)>& metadata_matches,
                          std::string&                             error,
                          const PackageRecord*                     floor = nullptr);

// Removes package_file and the record in plugin_dir. With floor (the record of
// the package the refused install replaced), writes floor there instead, so
// the version floor of the downgrade check survives the refusal.
void refuse_installed_package(const boost::filesystem::path& plugin_dir,
                              const boost::filesystem::path& package_file,
                              const PackageRecord*           floor);

// --- Wheel entry package ------------------------------------------------------

// The entry package name read from a wheel's metadata is safe to use as a
// folder name and an import name (is_safe_import_name()); the rule that closes
// the path escape. Checked where the name is chosen, so it does not ask the
// wheel to hold the package: upstream accepts a resource-only wheel (data
// files and dist-info, no Python package) there.
bool check_entry_package_name(const std::string& name, std::string& error);

// The entry package of a wheel is safe to extract to and import: a plain
// module name (check_entry_package_name()) that the wheel holds at its top, as
// a package folder or a module. The plugin folder is first on sys.path, so a
// regular package or a module held there is the one imported; a namespace
// folder can still lose to a regular package of that name later on the path
// (decision 0204, "Entry package guard"). Error messages are English, like
// the upstream wheel checks they join.
bool check_wheel_import_name(const boost::filesystem::path& wheel, const std::string& name, std::string& error);

// The entry is a wheel: its extension is .whl in any case.
bool is_wheel_path(const std::string& path);

// check_wheel_import_name() right before a plugin is imported, since the
// catalog may set the entry package of a cloud plugin: applied when entry_path is a wheel
// (any case of .whl), true for any other entry.
bool check_entry_package(const std::string& entry_path, const std::string& entry_package, std::string& error);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_logic_PluginTrust_hpp_
