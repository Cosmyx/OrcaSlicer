#ifndef slic3r_Cosmyx_BedTemperatureOff_hpp_
#define slic3r_Cosmyx_BedTemperatureOff_hpp_

// G-code side of the Cosmyx BedTemperatureOff feature. GCode.cpp sees this header through
// GCodeHooks.hpp. Its option definitions live in BedTemperatureOff.cpp
// (extend_bed_temperature_off()).
//
// A bed temperature of -1 means "bed heater off": the G-code turns the bed off
// with M140 S0 and never waits for it (no M190). A bed temperature of 0 keeps
// its upstream meaning: the filament does not support the plate type.
// See wiki/decisions/0010-bed-temperature-off.md.

#include <string>

namespace Slic3r {

class PlaceholderParser;

namespace Cosmyx {

// Bed temperature value that turns the bed heater off.
constexpr int bed_temperature_off = -1;

// True for a per-plate bed temperature option key: "*_plate_temp" and
// "*_plate_temp_initial_layer" (cool_plate_temp, hot_plate_temp_initial_layer, ...).
bool is_bed_temperature_key(const std::string& key);

// Clamps the bed temperature placeholders of the start and custom G-code
// templates to 0, so a bed turned off (-1) reads as 0 there and a template
// never emits "M190 S-1": bed_temperature, bed_temperature_initial_layer,
// bed_temperature_initial_layer_single and first_layer_bed_temperature.
// Placeholders that are not set are left alone.
void clamp_bed_temperature_placeholders(PlaceholderParser& parser);

} // namespace Cosmyx
} // namespace Slic3r

#endif // slic3r_Cosmyx_BedTemperatureOff_hpp_
