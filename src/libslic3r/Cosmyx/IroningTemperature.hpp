#ifndef slic3r_Cosmyx_IroningTemperature_hpp_
#define slic3r_Cosmyx_IroningTemperature_hpp_

// G-code side of the Cosmyx IroningTemperature feature. GCode.cpp sees this header through
// GCodeHooks.hpp. Its option definitions live in IroningTemperature.cpp
// (extend_ironing_temperature()).
//
// The filament option filament_ironing_temperature sets the nozzle temperature used while a
// filament irons; 0 keeps the print temperature. It is not a member of the static
// PrintConfig, so it is read by key from the print's full config.

#include <string>

#include "libslic3r/ExtrusionEntity.hpp"

namespace Slic3r {

class DynamicPrintConfig;
class GCode;

namespace Cosmyx {

// Key of the per-filament ironing temperature option.
extern const char* const ironing_temperature_key;

// Ironing temperature of filament_id in full, 0 when it is unset or the option is missing.
// The option is not variant-expanded, so it is indexed by filament id.
int ironing_temperature(const DynamicPrintConfig& full, unsigned int filament_id);

// True when at least one filament of full irons at its own temperature.
bool any_ironing_temperature(const DynamicPrintConfig& full);

// G-code to emit before a path of role `to` that follows a path of role `from`, for the
// filament gcodegen currently prints with. Entering erIroning with an ironing temperature
// above 0 sets that temperature without waiting; leaving erIroning restores the first layer
// or the normal nozzle temperature. Returns an empty string otherwise.
std::string ironing_temperature_gcode(const GCode& gcodegen, const DynamicPrintConfig& full, ExtrusionRole from,
                                      ExtrusionRole to, bool first_layer);

// G-code to emit before a tool change or a wipe tower block, which do not go through
// _extrude, while `last_role` is the role of the last path gcodegen printed. If that path
// was ironing at the current filament's ironing temperature, the current tool is set back
// to its print temperature, so it neither prints the tower nor sits at the ironing
// temperature until it is selected again.
std::string ironing_temperature_toolchange_gcode(const GCode& gcodegen, const DynamicPrintConfig& full,
                                                 ExtrusionRole last_role, bool first_layer);

} // namespace Cosmyx
} // namespace Slic3r

#endif // slic3r_Cosmyx_IroningTemperature_hpp_
