#ifndef slic3r_GUI_Cosmyx_CosmyxMachineHook_hpp_
#define slic3r_GUI_Cosmyx_CosmyxMachineHook_hpp_

// "Is the selected printer a Cosmyx machine?" for the GUI (decision 0222).
// Detection is Slic3r::Cosmyx::is_cosmyx_printer() (libslic3r/Cosmyx/
// CosmyxMachine.hpp) applied to the application's preset bundle.
//
// Tab::on_presets_changed() calls notify_printer_changed() through one hook
// line each time the printer presets change, the first load at startup
// included; subscribers hear about it only when the flag flips.

#include <functional>

#include "logic/FlipNotifier.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// True when the edited printer preset of wxGetApp().preset_bundle belongs to
// the Cosmyx vendor bundle. False while no preset bundle exists.
bool current_printer_is_cosmyx();

// Calls listener with the new flag each time it flips. The listener is not
// called on subscription: read current_printer_is_cosmyx() for the current
// state. Main thread only, like every caller of the hook.
FlipNotifier::Handle subscribe_printer_is_cosmyx(std::function<void(bool)> listener);
void                 unsubscribe_printer_is_cosmyx(FlipNotifier::Handle handle);

// Re-reads the flag and notifies the subscribers when it changed since the
// previous call (the first call always notifies). Called by the Tab.cpp hook.
void notify_printer_changed();

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_CosmyxMachineHook_hpp_
