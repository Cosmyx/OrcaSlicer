#ifndef slic3r_GUI_Cosmyx_CosmyxPrinterConnection_hpp_
#define slic3r_GUI_Cosmyx_CosmyxPrinterConnection_hpp_

// wxWidgets-free logic of the Cosmyx physical printer dialog (decision 0225):
// the machine address the user types, the print host URLs written to the
// printer preset, reading them back, the unlock rule of the "Machine
// information" tab and the classification of failed HTTP requests.
//
// The dialog itself lives in ../CosmyxPrinterConnectionDialog.cpp. This file
// depends on the standard library only; it is compiled into libslic3r_gui and
// into cosmyx_tests.

#include <optional>
#include <string>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Why a typed machine address was refused. The dialog maps each value to a
// translated message.
enum class HostError
{
    None,
    // Nothing typed (blanks only).
    Empty,
    // A space or a control character inside the address.
    Whitespace,
    // "http://..." or any other "<scheme>://".
    Scheme,
    // A '/', '?' or '#' after the host.
    Path,
    // "user@host".
    UserInfo,
    // A port that is not a number from 1 to 65535, or an empty one ("host:").
    Port,
    // Four dot-separated numbers that are not a valid IPv4 address.
    Ipv4,
    // Not an RFC 1123 host name (this also covers IPv6, which is not supported).
    Hostname,
};

struct HostCheck
{
    // Normalised "<host>[:<port>]": blanks around it removed, host name in
    // lower case, port without leading zeros. Empty unless error is None.
    std::string host;
    HostError   error = HostError::None;

    bool ok() const { return error == HostError::None; }
};

// Checks and normalises the "Machine IP" field: an IPv4 address or an
// RFC 1123 host name, optionally followed by ":<port>" (1-65535). Blanks
// around the value are ignored; anything else (scheme, path, user info,
// inner blanks, IPv6) is refused.
HostCheck check_host(const std::string& input);

// Why a typed API key was refused.
enum class ApiKeyError
{
    None,
    // A space or a control character inside the key.
    Whitespace,
};

struct ApiKeyCheck
{
    // The key without the blanks around it. An empty key is accepted: the
    // customer procedure always fills one, but the machine may not ask for it.
    std::string key;
    ApiKeyError error = ApiKeyError::None;

    bool ok() const { return error == ApiKeyError::None; }
};

ApiKeyCheck check_api_key(const std::string& input);

// URLs built from a normalised host ("<host>[:<port>]").
// OctoPrint-compatible print host: "http://<host>/octoprint/".
std::string octoprint_url(const std::string& host);
// Machine web interface shown in the Device tab: "http://<host>/mission-control-viewer/".
std::string mission_control_url(const std::string& host);
// CosmOS API endpoint: "http://<host>/" followed by path ("api/machine/device").
std::string cosmos_api_url(const std::string& host, const std::string& path);

// The host of a print_host value written by this dialog: "http://<host>/octoprint/"
// or "http://<host>/octoprint" (scheme case-insensitive), with a host accepted
// by check_host(). Anything else gives no host, and the dialog leaves the
// "Machine IP" field empty.
std::optional<std::string> host_from_octoprint_url(const std::string& url);

// What the Setup tab saves, and what a connection test checked.
struct ConnectionSettings
{
    std::string host;
    std::string api_key;

    bool operator==(const ConnectionSettings& other) const { return host == other.host && api_key == other.api_key; }
    bool operator!=(const ConnectionSettings& other) const { return !(*this == other); }
};

// The four printer preset values the Setup tab writes; every other print host
// key is left as it is.
struct PrintHostValues
{
    std::string host_type;        // "octoprint"
    std::string print_host;       // octoprint_url(host)
    std::string print_host_webui; // mission_control_url(host)
    std::string printhost_apikey; // the API key
};

PrintHostValues print_host_values(const ConnectionSettings& settings);

// The connection a saved printer preset describes, given its serialised
// host_type, print_host and printhost_apikey: set only when host_type is
// "octoprint" and print_host was written by this dialog.
std::optional<ConnectionSettings> saved_connection(const std::string& host_type,
                                                   const std::string& print_host,
                                                   const std::string& api_key);

// The "Machine information" tab is enabled once the Setup values are saved
// and a connection test (manual or automatic) succeeded with those same values.
bool machine_info_unlocked(const std::optional<ConnectionSettings>& saved,
                           const std::optional<ConnectionSettings>& last_successful_test);

// A failed HTTP request, for the message shown to the user.
enum class HttpFailure
{
    // HTTP 401: the API key is missing or wrong.
    Unauthorized,
    // HTTP 403: the key is valid but not allowed.
    Forbidden,
    // HTTP 404: the machine does not offer this endpoint.
    NotFound,
    // No answer in time.
    Timeout,
    // No connection at all (refused, unknown host, no route).
    Unreachable,
    // Any other HTTP error status.
    HttpError,
    // An answer that could not be read (unexpected status or body).
    BadResponse,
};

// status is the HTTP status (0 when no HTTP answer came) and curl_error the
// transport error text of the request, as Orca's Http class reports them.
HttpFailure classify_http_failure(unsigned status, const std::string& curl_error);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_CosmyxPrinterConnection_hpp_
