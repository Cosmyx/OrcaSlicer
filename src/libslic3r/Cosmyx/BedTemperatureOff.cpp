#include "ConfigDefExtensions.hpp"
#include "BedTemperatureOff.hpp"

#include "libslic3r/PrintConfig.hpp"

namespace Slic3r {
namespace Cosmyx {

void extend_bed_temperature_off(PrintConfigDef& def)
{
    // The feature defines its options here.
    (void) def;
}

} // namespace Cosmyx
} // namespace Slic3r
