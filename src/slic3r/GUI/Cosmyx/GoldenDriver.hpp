#ifndef slic3r_GUI_Cosmyx_GoldenDriver_hpp_
#define slic3r_GUI_Cosmyx_GoldenDriver_hpp_

// In-app driver of the GUI goldens (decisions 0162-0178,
// wiki/cosmyx/gui-goldens.md).
//
// When the environment variable COSMYX_GUI_DRIVER_DIR names a folder, the
// driver reads the script (COSMYX_GUI_DRIVER_SCRIPT, else <dir>/script.json),
// walks the application through every surface it lists and writes protocol v1
// events to <dir>/events.jsonl; the external harness
// (scripts/cosmyx/gui_goldens) captures the screen and acknowledges each
// capture with <dir>/ack-<seq>. Without the variable nothing happens, so a
// normal start of the application is unchanged.

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Starts the driver once, the first time it is called with the variable set;
// later calls do nothing. Called from GUI_App right after post_init(), which
// may run more than once on Linux.
void start_golden_driver_if_requested();

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_GoldenDriver_hpp_
