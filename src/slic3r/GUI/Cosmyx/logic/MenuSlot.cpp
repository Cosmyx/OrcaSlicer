#include "MenuSlot.hpp"

#include <algorithm>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

std::size_t slot_insert_position(const std::vector<int>& item_ids, int anchor_id, std::size_t saved_index)
{
    const auto it = std::find(item_ids.begin(), item_ids.end(), anchor_id);
    if (it != item_ids.end())
        return std::size_t(it - item_ids.begin()) + 1;
    return std::min(saved_index, item_ids.size());
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
