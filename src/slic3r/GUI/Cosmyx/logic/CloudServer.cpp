#include "CloudServer.hpp"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <string>
#include <utility>
#include <vector>

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

// An IPv4 address in its one dotted-decimal spelling: four parts 0-255, each
// without leading zeros. libcurl reads a part with a leading zero as octal,
// or, when that fails ("08"), hands the whole host to the resolver, so any
// other spelling is not a literal address to it.
bool read_ipv4(const std::string& text, std::array<std::uint8_t, 4>& bytes)
{
    std::size_t pos = 0;
    for (std::size_t i = 0; i < bytes.size(); ++i) {
        const std::size_t end  = text.find('.', pos);
        const std::string part = text.substr(pos, end == std::string::npos ? std::string::npos : end - pos);
        if (part.empty() || part.size() > 3 || !std::all_of(part.begin(), part.end(), is_digit) ||
            (part.size() > 1 && part.front() == '0') || std::stoi(part) > 255)
            return false;
        bytes[i] = static_cast<std::uint8_t>(std::stoi(part));
        if ((end == std::string::npos) != (i + 1 == bytes.size()))
            return false;
        pos = end + 1;
    }
    return true;
}

using Ipv6Groups = std::array<std::uint16_t, 8>;

// Hex groups of one side of an IPv6 address, the last one possibly a dotted
// IPv4 tail (two groups) when tail_allowed.
bool read_ipv6_groups(const std::string& text, bool tail_allowed, std::vector<std::uint16_t>& groups)
{
    if (text.empty())
        return true;
    std::size_t pos = 0;
    while (true) {
        const std::size_t end   = text.find(':', pos);
        const std::string field = text.substr(pos, end == std::string::npos ? std::string::npos : end - pos);
        if (end == std::string::npos && tail_allowed && field.find('.') != std::string::npos) {
            std::array<std::uint8_t, 4> v4{};
            if (!read_ipv4(field, v4))
                return false;
            groups.push_back(static_cast<std::uint16_t>(v4[0] << 8 | v4[1]));
            groups.push_back(static_cast<std::uint16_t>(v4[2] << 8 | v4[3]));
            return true;
        }
        if (field.empty() || field.size() > 4 ||
            !std::all_of(field.begin(), field.end(), [](char c) { return std::isxdigit(static_cast<unsigned char>(c)) != 0; }))
            return false;
        groups.push_back(static_cast<std::uint16_t>(std::stoul(field, nullptr, 16)));
        if (end == std::string::npos)
            return true;
        pos = end + 1;
    }
}

// An IPv6 address as inet_pton() reads it (RFC 4291 text form, no zone):
// eight hex groups of 1-4 digits, at most one "::" for one or more zero
// groups, and an optional dotted IPv4 tail in place of the last two groups.
// Written by hand: the logic stays free of OS socket headers.
bool read_ipv6(const std::string& text, Ipv6Groups& out)
{
    const std::size_t gap = text.find("::");
    if (gap != std::string::npos && text.find("::", gap + 1) != std::string::npos)
        return false;
    std::vector<std::uint16_t> head, tail;
    if (gap == std::string::npos) {
        if (!read_ipv6_groups(text, true, head) || head.size() != out.size())
            return false;
    } else if (!read_ipv6_groups(text.substr(0, gap), false, head) || !read_ipv6_groups(text.substr(gap + 2), true, tail) ||
               head.size() + tail.size() >= out.size()) {
        return false;
    }
    out.fill(0);
    std::copy(head.begin(), head.end(), out.begin());
    std::copy(tail.begin(), tail.end(), out.end() - static_cast<std::ptrdiff_t>(tail.size()));
    return true;
}

// The one spelling of an IPv6 address (RFC 5952): lower-case hex without
// leading zeros, the first longest run of two or more zero groups as "::".
// An IPv4 tail is written as hex groups.
std::string ipv6_text(const Ipv6Groups& groups)
{
    std::size_t best = groups.size(), best_len = 1;
    for (std::size_t i = 0; i < groups.size();) {
        std::size_t len = 0;
        while (i + len < groups.size() && groups[i + len] == 0)
            ++len;
        if (len > best_len) {
            best     = i;
            best_len = len;
        }
        i += len == 0 ? 1 : len;
    }
    static const char* const digits = "0123456789abcdef";
    std::string              text;
    for (std::size_t i = 0; i < groups.size(); ++i) {
        if (i == best) {
            text += "::";
            i += best_len - 1;
            continue;
        }
        if (!text.empty() && text.back() != ':')
            text += ':';
        std::string group;
        for (std::uint16_t value = groups[i]; group.empty() || value != 0; value = static_cast<std::uint16_t>(value >> 4))
            group.insert(group.begin(), digits[value & 0xf]);
        text += group;
    }
    return text;
}

bool is_ipv6_loopback(const std::string& text)
{
    Ipv6Groups groups{};
    return read_ipv6(text, groups) && groups == Ipv6Groups{0, 0, 0, 0, 0, 0, 0, 1};
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

// localhost, any name under .localhost (RFC 6761), 127.0.0.0/8 in its one
// dotted-decimal spelling and ::1 in any IPv6 spelling. Anything else is not
// loopback, even when some resolver would read it so: "localhost." (a name
// the resolver may send to DNS), an IPv4-mapped [::ffff:127.0.0.1] (whether
// it reaches 127.0.0.1 depends on the OS socket options) or a leading-zero
// 127.0.0.08, which libcurl resolves as a name.
bool is_loopback(const Authority& authority)
{
    const std::string name = to_lower(authority.host);
    if (authority.ipv6)
        return is_ipv6_loopback(name);
    const std::string           suffix = ".localhost";
    std::array<std::uint8_t, 4> v4{};
    return name == "localhost" ||
           (name.size() > suffix.size() && name.compare(name.size() - suffix.size(), suffix.size(), suffix) == 0) ||
           (read_ipv4(name, v4) && v4[0] == 127);
}

bool is_host_char(char c) { return std::isalnum(static_cast<unsigned char>(c)) != 0 || c == '-' || c == '_'; }

// A host name: dot-separated labels of host characters, one trailing dot
// allowed (a fully qualified name is the same host) and dropped.
bool read_host_name(std::string host, std::string& out)
{
    if (!host.empty() && host.back() == '.')
        host.pop_back();
    if (host.empty())
        return false;
    std::size_t pos = 0;
    while (true) {
        const std::size_t end   = host.find('.', pos);
        const std::string label = host.substr(pos, end == std::string::npos ? std::string::npos : end - pos);
        if (label.empty() || !std::all_of(label.begin(), label.end(), is_host_char))
            return false;
        if (end == std::string::npos)
            break;
        pos = end + 1;
    }
    out = to_lower(host);
    return true;
}

// A port as libcurl reads it: decimal digits, leading zeros allowed, 1-65535.
// Empty (host:) is the default port. The default port of scheme gives empty.
bool read_port(const std::string& port, const std::string& scheme, std::string& out)
{
    out.clear();
    if (port.empty())
        return true;
    if (!std::all_of(port.begin(), port.end(), is_digit))
        return false;
    const std::size_t first = port.find_first_not_of('0');
    if (first == std::string::npos || port.size() - first > 5)
        return false;
    const long number = std::stol(port.substr(first));
    if (number < 1 || number > 65535)
        return false;
    out = std::to_string(number);
    if ((scheme == "https" && number == 443) || (scheme == "http" && number == 80))
        out.clear();
    return true;
}

} // namespace

bool parse_server_address(const std::string& url, ServerAddress& address)
{
    const std::string text = trim_value(url);
    if (text.empty() || has_space_or_control(text) ||
        std::any_of(text.begin(), text.end(), [](char c) { return static_cast<unsigned char>(c) >= 0x80; }) ||
        text.find_first_of("%@?#\\") != std::string::npos)
        return false;

    const std::size_t marker = text.find("://");
    if (marker == std::string::npos)
        return false;
    ServerAddress result;
    result.scheme = to_lower(text.substr(0, marker));
    if (result.scheme != "https" && result.scheme != "http")
        return false;

    const std::size_t start     = marker + 3;
    const std::size_t slash     = text.find('/', start);
    const std::string authority = text.substr(start, slash == std::string::npos ? std::string::npos : slash - start);
    std::string       port;
    if (!authority.empty() && authority.front() == '[') {
        const std::size_t close = authority.find(']');
        Ipv6Groups        groups{};
        if (close == std::string::npos || !read_ipv6(authority.substr(1, close - 1), groups))
            return false;
        const std::string tail = authority.substr(close + 1);
        if (!tail.empty() && tail.front() != ':')
            return false;
        result.host = "[" + ipv6_text(groups) + "]";
        port        = tail.empty() ? std::string() : tail.substr(1);
    } else {
        const std::size_t colon = authority.find(':');
        if (colon != std::string::npos && authority.find(':', colon + 1) != std::string::npos)
            return false;
        if (!read_host_name(authority.substr(0, colon), result.host))
            return false;
        port = colon == std::string::npos ? std::string() : authority.substr(colon + 1);
    }
    if (!read_port(port, result.scheme, result.port))
        return false;

    std::string path = slash == std::string::npos ? std::string() : text.substr(slash);
    while (!path.empty() && path.back() == '/')
        path.pop_back();
    // libcurl removes dot segments before sending the path.
    for (std::size_t pos = 0; pos < path.size();) {
        const std::size_t end     = path.find('/', pos + 1);
        const std::string segment = path.substr(pos + 1, end == std::string::npos ? std::string::npos : end - pos - 1);
        if (segment == "." || segment == "..")
            return false;
        pos = end == std::string::npos ? path.size() : end;
    }
    result.path = path;
    address     = std::move(result);
    return true;
}

ServerKind server_kind(const std::string& url, ServerAddress* address)
{
    // apply_cloud_server() fills an empty key with CLOUD_SERVER_URL before the
    // agent reads it. A blank one is kept and used as it is, so it is not.
    if (url.empty())
        return ServerKind::Cosmyx;
    ServerAddress parsed, cosmyx;
    if (!parse_server_address(url, parsed))
        return ServerKind::Unrecognised;
    parse_server_address(CLOUD_SERVER_URL, cosmyx);
    if (address != nullptr)
        *address = parsed;
    // The Cosmyx host is decided by the parsed host, never by the spelling.
    // On that host only https on the default port is the Cosmyx server.
    if (parsed.host != cosmyx.host)
        return ServerKind::Custom;
    return parsed.scheme == cosmyx.scheme && parsed.port == cosmyx.port ? ServerKind::Cosmyx : ServerKind::Unrecognised;
}

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
    // Anything the plugin check would not recognise (decision 0204), by the
    // same rule as server_trust().
    if (server_kind(url) == ServerKind::Unrecognised)
        return CloudValueError::Invalid;
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
