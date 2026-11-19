#ifndef slic3r_GUI_Cosmyx_CosmyxModelsMenu_hpp_
#define slic3r_GUI_Cosmyx_CosmyxModelsMenu_hpp_

class wxMenu;
class wxWindow;

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Appends the top-level "Cosmyx 3D Models" submenu (Dual Head, Single Head and
// Handy groups) to `menu`. Idempotent: an item this function appended to the
// same menu before is destroyed first, so a menu rebuilt in place (see
// MenuFactory::update_default_menu) never shows the submenu twice. `parent` is
// the window that updates the menu items (MenuFactory's parent).
void append_models_submenu(wxMenu* menu, wxWindow* parent);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_CosmyxModelsMenu_hpp_
