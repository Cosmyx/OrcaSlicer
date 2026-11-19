#ifndef slic3r_GUI_Cosmyx_ColorMode_hpp_
#define slic3r_GUI_Cosmyx_ColorMode_hpp_

// GUI half of the always-on Cosmyx dark mode (decisions 0136, 0137, 0138).
// GUI_App::dark_mode() returns early through force_dark_mode(), so the
// application is dark on every OS whatever the system appearance, the saved
// config or the Windows Preferences toggle say.

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Pins the "dark_color_mode" app config key back to "1" if an upstream site
// overwrote it, and, on macOS and Linux, asks wxWidgets once for the dark
// native appearance. Always returns true, so the caller can write
// `if (Cosmyx::force_dark_mode()) return true;`.
bool force_dark_mode();

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_ColorMode_hpp_
