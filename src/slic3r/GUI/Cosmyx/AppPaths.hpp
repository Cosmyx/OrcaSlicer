#ifndef slic3r_GUI_Cosmyx_AppPaths_hpp_
#define slic3r_GUI_Cosmyx_AppPaths_hpp_

// GUI side of the Cosmyx data folder (see libslic3r/Cosmyx/DataDir.hpp).
// GUI_App.cpp includes this header through a single hook line; the header also
// brings DataDir.hpp, whose helpers the Linux hooks of GUI_App.cpp call.

#include "libslic3r/Cosmyx/DataDir.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Sets the application vendor name to "Cosmyx" and makes wxStandardPaths append
// both the vendor and the application name to its per-user folders, so
// GetUserDataDir() is %APPDATA%\Cosmyx\OrcaSlicer on Windows,
// ~/Library/Application Support/Cosmyx/OrcaSlicer on macOS and
// ~/.Cosmyx/OrcaSlicer on Linux. Called once, right after SetAppName(), before
// anything asks wxStandardPaths for a folder. Does nothing without a wxApp.
void use_vendor_data_dir();

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_AppPaths_hpp_
