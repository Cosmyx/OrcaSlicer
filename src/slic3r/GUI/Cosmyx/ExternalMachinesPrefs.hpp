#ifndef slic3r_GUI_Cosmyx_ExternalMachinesPrefs_hpp_
#define slic3r_GUI_Cosmyx_ExternalMachinesPrefs_hpp_

// "External machines" section of the Online tab of Preferences (decision 0219).
// PreferencesDialog::create_items() calls setup_external_machines() through one
// hook line, once upstream has added its rows.

class wxSizer;

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Gathers upstream's "Enable Bambu Cloud" row (`bambu_cloud_row`) and
// "Enable Bambu network plug-in" row (`network_plugin_row`) under one
// "External machines" title in `page`, the Online tab sizer, and makes both
// checkboxes ask for confirmation before they are turned on. The rows keep
// their upstream checkbox, setting and handler.
void setup_external_machines(wxSizer* page, wxSizer* bambu_cloud_row, wxSizer* network_plugin_row);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_ExternalMachinesPrefs_hpp_
