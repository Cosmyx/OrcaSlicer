#include "StealthMode.hpp"

#include "libslic3r/AppConfig.hpp"

namespace Slic3r {
namespace Cosmyx {

bool stealth_mode(const AppConfig& config)
{
    // Same first rule as upstream: always on until the setup guide is finished.
    if (!config.get_bool("firstguide", "finish"))
        return true;
    if (!config.has(STEALTH_SEEDED_KEY))
        return STEALTH_MODE_DEFAULT;
    return config.get_bool("stealth_mode");
}

bool seed_stealth_mode(AppConfig& config)
{
    if (config.has(STEALTH_SEEDED_KEY))
        return false;
    config.set_bool("stealth_mode", STEALTH_MODE_DEFAULT);
    config.set(STEALTH_SEEDED_KEY, "1");
    return true;
}

} // namespace Cosmyx
} // namespace Slic3r
