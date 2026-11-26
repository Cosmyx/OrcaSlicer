#ifndef slic3r_GUI_Cosmyx_UpdateCheckRequest_hpp_
#define slic3r_GUI_Cosmyx_UpdateCheckRequest_hpp_

// The Cosmyx update check (decision 0221). GUI_App::check_new_version_sf()
// calls it, through one hook line, in place of the upstream body, so the
// startup check and Help > Check for Updates both query the Cosmyx releases.

namespace Slic3r {

class AppConfig;

namespace GUI {

class VersionInfo;

namespace Cosmyx {

// Does nothing at startup in Stealth mode, and tells the user why when they
// asked (by_user != 0). Otherwise reads the Cosmyx GitHub releases in the
// background and, on the main thread, fills version_info and raises the
// upstream EVT_SLIC3R_VERSION_ONLINE popup for the newest real release newer
// than this build, or reports "newest version" to a user who asked.
void check_for_update(AppConfig& app_config, int by_user, VersionInfo& version_info);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_UpdateCheckRequest_hpp_
