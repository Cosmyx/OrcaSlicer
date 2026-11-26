#ifndef slic3r_GUI_Cosmyx_CosmyxVersion_hpp_
#define slic3r_GUI_Cosmyx_CosmyxVersion_hpp_

// Version shown to the user: the upstream OrcaSlicer version (SoftFever_VERSION
// from version.inc) followed by the Cosmyx patch number, e.g. "2.6.0-8", or
// "2.6.0-dev-8" on a development base (decisions 0060, 0061).
//
// SoftFever_VERSION itself is left alone: project files, presets and the
// updater parse it as an OrcaSlicer semver. Only the places that show the
// version to the user go through display_version().

#include <string>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Cosmyx patch number, raised by hand for each Cosmyx build that is handed
// out. It is the single source of the number: scripts/cosmyx/cosmyx_version.py
// reads this line to name the CI builds, so keep it on one line, as
// `patch_version = <integer>;`.
inline constexpr int patch_version = 8;

// "<upstream_version>-<patch>". The upstream pre-release suffix, if any, is
// kept: "2.6.0-dev" with patch 8 gives "2.6.0-dev-8".
std::string compose_display_version(const std::string& upstream_version, int patch);

// compose_display_version(SoftFever_VERSION, patch_version).
std::string display_version();

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_CosmyxVersion_hpp_
