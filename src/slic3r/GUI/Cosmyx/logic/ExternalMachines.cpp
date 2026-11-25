#include "ExternalMachines.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

bool external_toggle_needs_warning(bool turned_on) { return turned_on; }

ExternalToggleOutcome external_toggle_outcome(bool turned_on, bool confirmed)
{
    if (!external_toggle_needs_warning(turned_on))
        return {false, true};
    // A cancelled warning puts the toggle back off and the setting is never written.
    return confirmed ? ExternalToggleOutcome{true, true} : ExternalToggleOutcome{false, false};
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
