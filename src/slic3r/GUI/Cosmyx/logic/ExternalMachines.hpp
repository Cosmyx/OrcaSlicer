#ifndef slic3r_GUI_Cosmyx_logic_ExternalMachines_hpp_
#define slic3r_GUI_Cosmyx_logic_ExternalMachines_hpp_

// Rules of the "External machines" toggles of Preferences (decision 0219):
// "Enable Bambu Cloud" and "Enable Bambu network plug-in". Turning one on asks
// the user to confirm first, because Cosmyx does not maintain these modules;
// turning one off never asks. Free of wxWidgets, unit tested by cosmyx_tests.

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// What to do with a toggle the user has just clicked.
struct ExternalToggleOutcome
{
    // Value the checkbox must show once the click is handled.
    bool value;
    // True when the upstream handler must run (it saves the setting and
    // starts what the toggle controls); false when the click is cancelled.
    bool apply;
};

// True when the click turned the toggle on: the warning must be shown first.
bool external_toggle_needs_warning(bool turned_on);

// The outcome of a click. `confirmed` is the answer to the warning and is
// only read when external_toggle_needs_warning(turned_on) is true.
ExternalToggleOutcome external_toggle_outcome(bool turned_on, bool confirmed);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_logic_ExternalMachines_hpp_
