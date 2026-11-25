#include "CosmyxPrinterConnection.hpp"

#include <cctype>
#include <cstddef>
#include <string>
#include <vector>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

const char* const k_host_type_octoprint = "octoprint";
const char* const k_octoprint_path      = "/octoprint";

bool is_blank(char c)
{
    const unsigned char u = static_cast<unsigned char>(c);
    return u <= 0x20 || u == 0x7f;
}

bool is_digit(char c) { return c >= '0' && c <= '9'; }

std::string trim_blanks(const std::string& s)
{
    std::size_t begin = 0;
    std::size_t end   = s.size();
    while (begin < end && is_blank(s[begin]))
        ++begin;
    while (end > begin && is_blank(s[end - 1]))
        --end;
    return s.substr(begin, end - begin);
}

bool has_blank(const std::string& s)
{
    for (char c : s)
        if (is_blank(c))
            return true;
    return false;
}

std::string to_lower(std::string s)
{
    for (char& c : s)
        if (c >= 'A' && c <= 'Z')
            c = static_cast<char>(c - 'A' + 'a');
    return s;
}

std::vector<std::string> split(const std::string& s, char separator)
{
    std::vector<std::string> parts;
    std::size_t              start = 0;
    for (;;) {
        const std::size_t pos = s.find(separator, start);
        parts.push_back(s.substr(start, pos == std::string::npos ? std::string::npos : pos - start));
        if (pos == std::string::npos)
            return parts;
        start = pos + 1;
    }
}

bool all_digits(const std::string& s)
{
    if (s.empty())
        return false;
    for (char c : s)
        if (!is_digit(c))
            return false;
    return true;
}

// Port text to its canonical decimal form, or empty when it is not 1-65535.
std::string normalise_port(const std::string& port)
{
    if (!all_digits(port))
        return {};
    std::size_t first = port.find_first_not_of('0');
    if (first == std::string::npos)
        return {};
    const std::string digits = port.substr(first);
    if (digits.size() > 5)
        return {};
    const unsigned long value = std::stoul(digits);
    return value >= 1 && value <= 65535 ? digits : std::string();
}

bool valid_ipv4(const std::vector<std::string>& labels)
{
    if (labels.size() != 4)
        return false;
    for (const std::string& label : labels) {
        // Leading zeros are refused: "010" reads as octal in some resolvers.
        if (!all_digits(label) || label.size() > 3 || (label.size() > 1 && label[0] == '0'))
            return false;
        if (std::stoul(label) > 255)
            return false;
    }
    return true;
}

bool valid_hostname_label(const std::string& label)
{
    if (label.empty() || label.size() > 63 || label.front() == '-' || label.back() == '-')
        return false;
    for (char c : label)
        if (!((c >= 'a' && c <= 'z') || is_digit(c) || c == '-'))
            return false;
    return true;
}

// host is lower case, without a port.
HostError check_host_name(const std::string& host)
{
    if (host.empty())
        return HostError::Hostname;
    const std::vector<std::string> labels = split(host, '.');
    bool numeric = true;
    for (const std::string& label : labels)
        numeric = numeric && all_digits(label);
    if (numeric)
        return valid_ipv4(labels) ? HostError::None : HostError::Ipv4;
    if (host.size() > 253)
        return HostError::Hostname;
    for (const std::string& label : labels)
        if (!valid_hostname_label(label))
            return HostError::Hostname;
    // A top-level label made of digits only is an IP address typo, not a name.
    if (all_digits(labels.back()))
        return HostError::Hostname;
    return HostError::None;
}

bool starts_with_ci(const std::string& s, const std::string& prefix)
{
    return s.size() >= prefix.size() && to_lower(s.substr(0, prefix.size())) == prefix;
}

} // namespace

HostCheck check_host(const std::string& input)
{
    HostCheck         result;
    const std::string value = trim_blanks(input);
    if (value.empty()) {
        result.error = HostError::Empty;
        return result;
    }
    if (has_blank(value)) {
        result.error = HostError::Whitespace;
        return result;
    }
    if (value.find("://") != std::string::npos) {
        result.error = HostError::Scheme;
        return result;
    }
    if (value.find_first_of("/?#\\") != std::string::npos) {
        result.error = HostError::Path;
        return result;
    }
    if (value.find('@') != std::string::npos) {
        result.error = HostError::UserInfo;
        return result;
    }

    std::string       host = to_lower(value);
    std::string       port;
    const std::size_t colon = host.find(':');
    if (colon != std::string::npos) {
        // More than one colon is an IPv6 address, which is not supported.
        if (host.find(':', colon + 1) != std::string::npos || host.find_first_of("[]") != std::string::npos) {
            result.error = HostError::Hostname;
            return result;
        }
        port = normalise_port(host.substr(colon + 1));
        host = host.substr(0, colon);
        if (port.empty()) {
            result.error = HostError::Port;
            return result;
        }
    }

    result.error = check_host_name(host);
    if (result.ok())
        result.host = port.empty() ? host : host + ":" + port;
    return result;
}

ApiKeyCheck check_api_key(const std::string& input)
{
    ApiKeyCheck result;
    result.key = trim_blanks(input);
    if (has_blank(result.key)) {
        result.key.clear();
        result.error = ApiKeyError::Whitespace;
    }
    return result;
}

std::string octoprint_url(const std::string& host) { return "http://" + host + k_octoprint_path + "/"; }

std::string mission_control_url(const std::string& host) { return "http://" + host + "/mission-control-viewer/"; }

std::string cosmos_api_url(const std::string& host, const std::string& path) { return "http://" + host + "/" + path; }

std::optional<std::string> host_from_octoprint_url(const std::string& url)
{
    const std::string scheme = "http://";
    if (!starts_with_ci(url, scheme))
        return std::nullopt;
    std::string rest = url.substr(scheme.size());
    if (!rest.empty() && rest.back() == '/')
        rest.pop_back();
    const std::string suffix = k_octoprint_path;
    if (rest.size() <= suffix.size() || rest.compare(rest.size() - suffix.size(), suffix.size(), suffix) != 0)
        return std::nullopt;
    const std::string host = rest.substr(0, rest.size() - suffix.size());
    // The host part must be the whole authority: no blanks, no path, nothing to trim.
    if (host != trim_blanks(host))
        return std::nullopt;
    const HostCheck check = check_host(host);
    if (!check.ok())
        return std::nullopt;
    return check.host;
}

PrintHostValues print_host_values(const ConnectionSettings& settings)
{
    return {k_host_type_octoprint, octoprint_url(settings.host), mission_control_url(settings.host), settings.api_key};
}

std::optional<ConnectionSettings> saved_connection(const std::string& host_type,
                                                   const std::string& print_host,
                                                   const std::string& api_key)
{
    if (host_type != k_host_type_octoprint)
        return std::nullopt;
    const std::optional<std::string> host = host_from_octoprint_url(print_host);
    if (!host)
        return std::nullopt;
    return ConnectionSettings{*host, api_key};
}

bool machine_info_unlocked(const std::optional<ConnectionSettings>& saved,
                           const std::optional<ConnectionSettings>& last_successful_test)
{
    return saved.has_value() && last_successful_test.has_value() && *saved == *last_successful_test;
}

HttpFailure classify_http_failure(unsigned status, const std::string& curl_error)
{
    switch (status) {
    case 401: return HttpFailure::Unauthorized;
    case 403: return HttpFailure::Forbidden;
    case 404: return HttpFailure::NotFound;
    default: break;
    }
    if (status >= 400)
        return HttpFailure::HttpError;
    if (status != 0)
        return HttpFailure::BadResponse;
    if (curl_error.empty())
        return HttpFailure::BadResponse;
    const std::string error = to_lower(curl_error);
    if (error.find("timeout") != std::string::npos || error.find("timed out") != std::string::npos)
        return HttpFailure::Timeout;
    return HttpFailure::Unreachable;
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
