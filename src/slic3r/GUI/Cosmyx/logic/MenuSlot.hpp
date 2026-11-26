#ifndef slic3r_GUI_Cosmyx_MenuSlot_hpp_
#define slic3r_GUI_Cosmyx_MenuSlot_hpp_

// Where a menu item that was taken out of a menu goes back in. The Cosmyx
// models submenu is removed from the context menus while the selected printer
// is not a Cosmyx machine, and put back right after the item it followed when
// it was first built ("Add Handy models"), not at the end (decision 0223).
//
// wxWidgets-free: compiled into libslic3r_gui and into cosmyx_tests.

#include <cstddef>
#include <vector>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Position to insert at, given the ids of the items now in the menu in order:
// right after the item whose id is anchor_id when it is still there; else
// saved_index (where the item stood), clamped to the end of the menu.
std::size_t slot_insert_position(const std::vector<int>& item_ids, int anchor_id, std::size_t saved_index);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_MenuSlot_hpp_
