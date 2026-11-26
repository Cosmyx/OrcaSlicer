#ifndef slic3r_Cosmyx_ColorModeDefault_hpp_
#define slic3r_Cosmyx_ColorModeDefault_hpp_

// Cosmyx always runs in dark mode, on every OS, for fresh and existing configs
// alike, and the user cannot turn it off (decisions 0136, 0137). This is the
// wxWidgets-free half: it pins the "dark_color_mode" app config key, which
// about ten upstream places read directly instead of calling
// GUI_App::dark_mode(). The GUI half lives in src/slic3r/GUI/Cosmyx/ColorMode.

namespace Slic3r {

class AppConfig;

namespace Cosmyx {

// Value "dark_color_mode" is pinned to ("1" means dark).
inline constexpr const char* forced_dark_color_mode = "1";

// Sets "dark_color_mode" to "1" whatever it holds (empty, "0", anything else).
// Returns true when the value had to change. Called from
// AppConfig::set_defaults(), which runs after every load and reset, and again
// by the GUI each time GUI_App::dark_mode() is asked, which heals any upstream
// site that wrote "0" in between.
bool force_dark_color_mode(AppConfig& config);

} // namespace Cosmyx
} // namespace Slic3r

#endif // slic3r_Cosmyx_ColorModeDefault_hpp_
