#include "CloudServer.hpp"

#include <algorithm>
#include <cctype>

#include "libslic3r/AppConfig.hpp"
#include "libslic3r/Cosmyx/StealthMode.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

constexpr const char* HTTPS = "https://";

std::string seeded_key(std::size_t field) { return std::string(SEEDED_PREFIX) + CLOUD_KEYS[field]; }
std::string custom_key(std::size_t field) { return std::string(CUSTOM_PREFIX) + CLOUD_KEYS[field]; }

bool is_space(char c) { return std::isspace(static_cast<unsigned char>(c)) != 0; }

bool has_space_or_control(const std::string& value)
{
    return std::any_of(value.begin(), value.end(), [](char c) {
        const auto u = static_cast<unsigned char>(c);
        return std::isspace(u) != 0 || std::iscntrl(u) != 0;
    });
}

bool starts_with_https(const std::string& url)
{
    const std::size_t n = std::char_traits<char>::length(HTTPS);
    if (url.size() < n)
        return false;
    for (std::size_t i = 0; i < n; ++i)
        if (std::tolower(static_cast<unsigned char>(url[i])) != HTTPS[i])
            return false;
    return true;
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
    return written;
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
    if (!starts_with_https(url))
        return CloudValueError::NotHttps;
    if (has_space_or_control(url))
        return CloudValueError::Invalid;

    const std::string rest      = url.substr(std::char_traits<char>::length(HTTPS));
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
        host = authority.substr(1, close - 1);
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
        if (port.size() > 5 || !std::all_of(port.begin(), port.end(), [](char c) { return c >= '0' && c <= '9'; }))
            return CloudValueError::Invalid;
        const long number = std::stol(port);
        if (number < 1 || number > 65535)
            return CloudValueError::Invalid;
    }
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
        if (starts_with_https(value)) {
            value.replace(0, std::char_traits<char>::length(HTTPS), HTTPS);
            while (value.size() > std::char_traits<char>::length(HTTPS) && value.back() == '/')
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
