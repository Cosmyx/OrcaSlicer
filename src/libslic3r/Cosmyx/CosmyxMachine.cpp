#include "CosmyxMachine.hpp"

#include <string>

#include "libslic3r/Preset.hpp"
#include "libslic3r/PresetBundle.hpp"

namespace Slic3r {
namespace Cosmyx {

const char* const COSMYX_VENDOR_ID = "Cosmyx";

bool is_cosmyx_vendor(const VendorProfile* vendor)
{
    return vendor != nullptr && vendor->id == COSMYX_VENDOR_ID;
}

bool is_cosmyx_printer(const PresetBundle& bundle)
{
    // Walks the "inherits" chain up to the first preset with a vendor, so a
    // user preset derived from a Cosmyx system preset counts.
    return is_cosmyx_vendor(bundle.printers.get_edited_preset_with_vendor_profile().vendor);
}

} // namespace Cosmyx
} // namespace Slic3r
