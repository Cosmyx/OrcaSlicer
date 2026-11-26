#include "ColorModeDefault.hpp"

#include "libslic3r/AppConfig.hpp"

#include <string>

namespace Slic3r {
namespace Cosmyx {

bool force_dark_color_mode(AppConfig& config)
{
    if (config.get("dark_color_mode") == forced_dark_color_mode)
        return false;
    config.set("dark_color_mode", std::string(forced_dark_color_mode));
    return true;
}

} // namespace Cosmyx
} // namespace Slic3r
