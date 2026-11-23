#include "CloudServer.hpp"

#include <algorithm>
#include <cctype>
#include <mutex>
#include <string>

#include "libslic3r/AppConfig.hpp"
#include "libslic3r/Cosmyx/StealthMode.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

constexpr const char* HTTPS = "https://";
constexpr const char* HTTP  = "http://";

std::mutex& active_api_url_mutex()
{
    static std::mutex mutex;
    return mutex;
}

std::string& active_api_url_value()
{
    static std::string value;
    return value;
}

std::string seeded_key(std::size_t field) { return std::string(SEEDED_PREFIX) + CLOUD_KEYS[field]; }
std::string custom_key(std::size_t field) { return std::string(CUSTOM_PREFIX) + CLOUD_KEYS[field]; }

bool is_space(char c) { return std::isspace(static_cast<unsigned char>(c)) != 0; }
bool is_digit(char c) { return c >= '0' && c <= '9'; }

std::string to_lower(std::string value)
{
    for (char& c : value)
        c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
    return value;
}

bool has_space_or_control(const std::string& value)
{
    return std::any_of(value.begin(), value.end(), [](char c) {
        const auto u = static_cast<unsigned char>(c);
        return std::isspace(u) != 0 || std::iscntrl(u) != 0;
    });
}

// Case-insensitive prefix test; scheme is lower case.
bool starts_with_scheme(const std::string& url, const char* scheme)
{
    const std::size_t n = std::char_traits<char>::length(scheme);
    return url.size() >= n && to_lower(url.substr(0, n)) == scheme;
}

// The scheme prefix of url ("https://" or "http://"), or nullptr.
const char* url_scheme(const std::string& url)
{
    if (starts_with_scheme(url, HTTPS))
        return HTTPS;
    if (starts_with_scheme(url, HTTP))
        return HTTP;
    return nullptr;
}

// 127.0.0.0/8 written as four decimal octets.
bool is_loopback_ipv4(const std::string& host)
{
    int         octets = 0;
    std::size_t pos    = 0;
    while (true) {
        const std::size_t end = host.find('.', pos);
        const std::string part = host.substr(pos, end == std::string::npos ? std::string::npos : end - pos);
        if (part.empty() || part.size() > 3 || !std::all_of(part.begin(), part.end(), is_digit) || std::stoi(part) > 255)
            return false;
        if (octets == 0 && part != "127")
            return false;
        ++octets;
        if (end == std::string::npos)
            break;
        pos = end + 1;
    }
    return octets == 4;
}

struct Authority
{
    std::string host; // without the IPv6 brackets
    bool        ipv6 = false;
};

// Parses the authority of url after its scheme prefix of length skip:
// [user info is refused] host or [IPv6], then an optional port 1-65535.
CloudValueError parse_authority(const std::string& url, std::size_t skip, Authority& out)
{
    const std::string rest      = url.substr(skip);
    const std::string authority = rest.substr(0, rest.find_first_of("/?#"));
    if (authority.find('@') != std::string::npos)
        return CloudValueError::Invalid;

    std::string host = authority;
    std::string port;
    if (!authority.empty() && authority.front() == '[') {
        // IPv6 literal: [address] or [address]:port
        const std::size_t close = authority.find(']');
        if (close == std::string::npos)
            return CloudValueError::Invalid;
        host     = authority.substr(1, close - 1);
        out.ipv6 = true;
        const std::string tail = authority.substr(close + 1);
        if (!tail.empty()) {
            if (tail.front() != ':')
                return CloudValueError::Invalid;
            port = tail.substr(1);
            if (port.empty())
                return CloudValueError::Invalid;
        }
    } else if (const std::size_t colon = authority.find(':'); colon != std::string::npos) {
        host = authority.substr(0, colon);
        port = authority.substr(colon + 1);
        if (port.empty())
            return CloudValueError::Invalid;
    }
    if (host.empty())
        return CloudValueError::NoHost;
    if (!port.empty()) {
        if (port.size() > 5 || !std::all_of(port.begin(), port.end(), is_digit))
            return CloudValueError::Invalid;
        const long number = std::stol(port);
        if (number < 1 || number > 65535)
            return CloudValueError::Invalid;
    }
    out.host = host;
    return CloudValueError::None;
}

// localhost, any name under .localhost (RFC 6761), 127.0.0.0/8 and [::1].
bool is_loopback(const Authority& authority)
{
    const std::string name = to_lower(authority.host);
    if (authority.ipv6)
        return name == "::1";
    const std::string suffix = ".localhost";
    return name == "localhost" ||
           (name.size() > suffix.size() && name.compare(name.size() - suffix.size(), suffix.size(), suffix) == 0) ||
           is_loopback_ipv4(name);
}

} // namespace

int apply_cloud_server(AppConfig& config)
{
    ::Slic3r::Cosmyx::seed_stealth_mode(config);

    const bool        custom   = custom_cloud_enabled(config);
    const CloudValues defaults = cosmocloud_values();
    int               written  = 0;
    for (std::size_t field = 0; field < CLOUD_FIELD_COUNT; ++field) {
        const std::string current = config.get(CLOUD_KEYS[field]);
        // A value Cosmyx did not write is the user's: it wins.
        if (!current.empty() && (custom || current != config.get(seeded_key(field))))
            continue;
        if (current != defaults[field]) {
            config.set(CLOUD_KEYS[field], defaults[field]);
            ++written;
        }
        config.set(seeded_key(field), defaults[field]);
    }
    {
        std::lock_guard<std::mutex> lock(active_api_url_mutex());
        active_api_url_value() = config.get(CLOUD_KEYS[ApiUrl]);
    }
    return written;
}

std::string active_api_url(const AppConfig& config)
{
    {
        std::lock_guard<std::mutex> lock(active_api_url_mutex());
        if (!active_api_url_value().empty())
            return active_api_url_value();
    }
    return config.get(CLOUD_KEYS[ApiUrl]);
}

std::string trim_value(const std::string& value)
{
    auto begin = std::find_if_not(value.begin(), value.end(), is_space);
    auto end   = std::find_if_not(value.rbegin(), value.rend(), is_space).base();
    return begin < end ? std::string(begin, end) : std::string();
}

CloudValueError check_cloud_url(const std::string& url)
{
    if (url.empty())
        return CloudValueError::Empty;
    const char* scheme = url_scheme(url);
    if (scheme == nullptr)
        return CloudValueError::NotHttps;
    if (has_space_or_control(url))
        return CloudValueError::Invalid;

    Authority             authority;
    const CloudValueError error = parse_authority(url, std::char_traits<char>::length(scheme), authority);
    if (error != CloudValueError::None)
        return error;
    // Plain http is allowed only on a loopback host, where it never leaves the machine.
    if (scheme == HTTP && !is_loopback(authority))
        return CloudValueError::NotHttps;
    return CloudValueError::None;
}

CloudValueError check_pub_key(const std::string& key)
{
    if (key.empty())
        return CloudValueError::Empty;
    if (has_space_or_control(key))
        return CloudValueError::Invalid;
    return CloudValueError::None;
}

CloudValidation normalize_cloud_values(CloudValues& values)
{
    for (std::string& value : values)
        value = trim_value(value);
    for (std::size_t field = 0; field < CLOUD_FIELD_COUNT; ++field) {
        std::string& value = values[field];
        if (field == PubKey)
            continue;
        if (!value.empty() && value.find("://") == std::string::npos) {
            // No scheme: http for a loopback host, https for any other.
            Authority authority;
            const bool loopback = parse_authority(value, 0, authority) == CloudValueError::None && is_loopback(authority);
            value.insert(0, loopback ? HTTP : HTTPS);
        }
        if (const char* scheme = url_scheme(value)) {
            const std::size_t n = std::char_traits<char>::length(scheme);
            value.replace(0, n, scheme);
            while (value.size() > n && value.back() == '/')
                value.pop_back();
        }
    }

    CloudValidation result;
    for (std::size_t field = 0; field < CLOUD_FIELD_COUNT; ++field) {
        const CloudValueError error = field == PubKey ? check_pub_key(values[field]) : check_cloud_url(values[field]);
        if (error != CloudValueError::None) {
            result.error = error;
            result.field = field;
            break;
        }
    }
    return result;
}

bool custom_cloud_enabled(const AppConfig& config) { return config.get_bool(CUSTOM_CLOUD_KEY); }

CloudValues custom_cloud_values(const AppConfig& config)
{
    const bool  custom = custom_cloud_enabled(config);
    CloudValues values;
    for (std::size_t field = 0; field < CLOUD_FIELD_COUNT; ++field)
        values[field] = config.get(custom ? std::string(CLOUD_KEYS[field]) : custom_key(field));
    return values;
}

void use_custom_cloud(AppConfig& config, const CloudValues& values)
{
    config.set_bool(CUSTOM_CLOUD_KEY, true);
    for (std::size_t field = 0; field < CLOUD_FIELD_COUNT; ++field) {
        config.set(CLOUD_KEYS[field], values[field]);
        config.set(custom_key(field), values[field]);
    }
}

void use_cosmocloud(AppConfig& config)
{
    config.set_bool(CUSTOM_CLOUD_KEY, false);
    const CloudValues defaults = cosmocloud_values();
    for (std::size_t field = 0; field < CLOUD_FIELD_COUNT; ++field) {
        config.set(CLOUD_KEYS[field], defaults[field]);
        config.set(seeded_key(field), defaults[field]);
    }
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
