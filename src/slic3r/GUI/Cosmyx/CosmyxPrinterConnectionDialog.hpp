#ifndef slic3r_GUI_Cosmyx_CosmyxPrinterConnectionDialog_hpp_
#define slic3r_GUI_Cosmyx_CosmyxPrinterConnectionDialog_hpp_

// Cosmyx physical printer dialog (decision 0225). On a Cosmyx printer the
// "Connection" button of the printer title bar opens it instead of upstream's
// PhysicalPrinterDialog, through one hook line in Plater.cpp. It has two tabs:
// "Setup" (preset name, machine address, API key, connection test) and
// "Machine information" (identity, installed options, hot ends and camera read
// from the CosmOS API of the machine).

class wxWindow;

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Shows the Cosmyx physical printer dialog, modal, when the selected printer
// is a Cosmyx machine, and returns true once it is closed. Returns false at
// once, showing nothing, for any other printer: the caller then shows the
// upstream dialog.
bool show_cosmyx_printer_dialog(wxWindow* parent);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_CosmyxPrinterConnectionDialog_hpp_
