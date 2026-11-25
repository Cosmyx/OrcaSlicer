#ifndef slic3r_GUI_Cosmyx_CloudServerPrefs_hpp_
#define slic3r_GUI_Cosmyx_CloudServerPrefs_hpp_

// "Custom Cloud Instance" rows of the Online tab of Preferences
// (decision 0203). PreferencesDialog::create_items() adds the panel to the
// Connection section through one hook line.

class wxWindow;

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Creates the panel as a child of the Preferences scrolled page. The panel
// reads and writes wxGetApp().app_config itself.
wxWindow* create_cloud_server_prefs(wxWindow* parent);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_CloudServerPrefs_hpp_
