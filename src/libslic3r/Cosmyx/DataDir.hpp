#ifndef slic3r_Cosmyx_DataDir_hpp_
#define slic3r_Cosmyx_DataDir_hpp_

// Where a Cosmyx build keeps its user data. Every OS nests the data folder under a
// "Cosmyx" vendor folder, so a Cosmyx build never shares its presets, login or
// plugins with an upstream OrcaSlicer install on the same machine:
//   Windows: %APPDATA%\Cosmyx\OrcaSlicer
//   macOS:   ~/Library/Application Support/Cosmyx/OrcaSlicer
//   Linux:   $XDG_CONFIG_HOME/Cosmyx/OrcaSlicer (~/.config/Cosmyx/OrcaSlicer)
// The data folder itself keeps the upstream name (SLIC3R_APP_KEY).
//
// Windows and macOS get the nesting from wxStandardPaths (GUI/Cosmyx/AppPaths);
// Linux builds its path with xdg_config_dir() (utils.cpp, default_data_dir()).
// See wiki/cosmyx/install-and-data-paths.md.

#include <string>

namespace Slic3r {
namespace Cosmyx {

// Name of the vendor folder that holds the data folder, on every OS.
inline constexpr const char *DATA_DIR_VENDOR = "Cosmyx";

// "Cosmyx/<app_key>", joined with the native separator: the data folder relative
// to the per-user config root (XDG_CONFIG_HOME on Linux).
std::string vendor_app_subdir(const std::string &app_key);

// The same path with its vendor folder taken out: "<base>/Cosmyx/<leaf>" becomes
// "<base>/<leaf>". A path whose parent folder is not the vendor folder comes back
// unchanged. Used to find where a data folder lived before it was nested, such as
// the legacy Flatpak data folder.
std::string without_vendor_dir(const std::string &data_dir);

} // namespace Cosmyx
} // namespace Slic3r

#endif // slic3r_Cosmyx_DataDir_hpp_
