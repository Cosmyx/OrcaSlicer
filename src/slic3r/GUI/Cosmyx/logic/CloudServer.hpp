#ifndef slic3r_GUI_Cosmyx_logic_CloudServer_hpp_
#define slic3r_GUI_Cosmyx_logic_CloudServer_hpp_

// Points the Orca cloud agent at the Cosmyx CosmoCloud server (decision 0201),
// unless the user chose a custom cloud instance in Preferences (decision 0203).
//
// OrcaCloudServiceAgent::configure_urls() reads the app keys orca_api_url,
// orca_auth_url, orca_cloud_url and orca_pub_key once, when the agent is
// created, and keeps its upstream default for an empty key.
// apply_cloud_server() runs right before create_agent_from_config() in
// GUI_App::on_init_network(), through one hook line, and fills those keys:
//
// - with the custom instance on (CUSTOM_CLOUD_KEY), only an empty key gets the
//   CosmoCloud value, so the agent never falls back to the upstream cloud;
// - otherwise a key that is empty, or that still holds the value Cosmyx wrote
//   there last time, gets the current CosmoCloud value, and any other value
//   was set by the user by hand and is left as it is.
//
// The value written is remembered under SEEDED_PREFIX + key, so a later change
// of a CosmoCloud constant reaches existing installs without ever overwriting
// a user's value. apply_cloud_server() also seeds the Cosmyx stealth mode
// default (decision 0200).
//
// wxWidgets-free, so cosmyx_tests checks it directly.

#include <array>
#include <cstddef>
#include <string>

namespace Slic3r {

class AppConfig;

namespace GUI {
namespace Cosmyx {

// One host serves the API, the auth server and the web pages.
constexpr const char* CLOUD_SERVER_URL = "https://orca-cloud.cosmyx3d.fr";

// Public key sent as the apikey header; it is not a secret. This is the
// CosmoCloud development value: a release build must replace it with the
// production key (decision 0202). scripts/cosmyx/tests/test_cloud_server.py
// warns while it is still the placeholder.
constexpr const char* CLOUD_PUB_KEY = "cosmocloud-public-key";

// Prefix of the app keys that remember what Cosmyx wrote to each cloud key.
constexpr const char* SEEDED_PREFIX = "cosmyx_seeded_";

// Bool app key: the user's custom cloud instance is on (Preferences).
constexpr const char* CUSTOM_CLOUD_KEY = "cosmyx_custom_cloud";

// Prefix of the app keys that keep the custom values while the custom instance
// is off, so turning it on again shows them back.
constexpr const char* CUSTOM_PREFIX = "cosmyx_custom_";

// The cloud keys, in the order of CloudValues.
enum CloudField : std::size_t { ApiUrl = 0, AuthUrl = 1, CloudUrl = 2, PubKey = 3 };
constexpr std::size_t CLOUD_FIELD_COUNT = 4;

using CloudValues = std::array<std::string, CLOUD_FIELD_COUNT>;

// The app keys read by OrcaCloudServiceAgent::configure_urls().
constexpr std::array<const char*, CLOUD_FIELD_COUNT> CLOUD_KEYS = {
    "orca_api_url", "orca_auth_url", "orca_cloud_url", "orca_pub_key"};

// The CosmoCloud value of each key.
inline CloudValues cosmocloud_values()
{
    return {CLOUD_SERVER_URL, CLOUD_SERVER_URL, CLOUD_SERVER_URL, CLOUD_PUB_KEY};
}

// Fills the cloud keys as described above and seeds the stealth mode default.
// Returns the number of cloud keys written.
int apply_cloud_server(AppConfig& config);

// The API address the cloud agent was created with: orca_api_url as
// apply_cloud_server() left it, which the agent reads right after. A change in
// Preferences only reaches the agent at the next start (decision 0203), so the
// plugin package check (decision 0204) uses this address, not the current key.
// Before the first apply_cloud_server(), the current orca_api_url.
std::string active_api_url(const AppConfig& config);

// --- Custom cloud instance (Preferences, decision 0203) ---------------------

enum class CloudValueError {
    None,
    Empty,    // nothing entered
    NotHttps, // not https://, and not http:// on a loopback host
    NoHost,   // a scheme with no host name
    Invalid,  // spaces, user info, a bad port
};

struct CloudValidation
{
    CloudValueError error = CloudValueError::None;
    std::size_t     field = 0; // the first field in error
    bool            ok() const { return error == CloudValueError::None; }
};

// Leading and trailing spaces, tabs and line breaks removed.
std::string trim_value(const std::string& value);

// Checks a trimmed address: https scheme (any case), or http on a loopback
// host (localhost, *.localhost, 127.0.0.0/8, [::1]) for a local test server;
// a host name, an optional port 1-65535, no spaces and no user info.
CloudValueError check_cloud_url(const std::string& url);

// Checks a trimmed public key: not empty, no spaces.
CloudValueError check_pub_key(const std::string& key);

// Trims every value, adds a missing scheme to an address ("http://" for a
// loopback host, else "https://"), writes the scheme in lower case and drops
// trailing slashes (the agent appends paths starting with '/'), then checks
// the values in field order and reports the first error. An explicit scheme
// is never changed.
CloudValidation normalize_cloud_values(CloudValues& values);

bool custom_cloud_enabled(const AppConfig& config);

// The values Preferences shows: the cloud keys while the custom instance is on,
// else the custom values kept from the last time it was on.
CloudValues custom_cloud_values(const AppConfig& config);

// Turns the custom instance on with normalized values: writes them to the
// cloud keys and keeps a copy under CUSTOM_PREFIX.
void use_custom_cloud(AppConfig& config, const CloudValues& values);

// Turns the custom instance off: the cloud keys get the CosmoCloud values,
// owned by Cosmyx again; the custom copy is kept.
void use_cosmocloud(AppConfig& config);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_logic_CloudServer_hpp_
