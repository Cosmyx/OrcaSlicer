// G-code side of the per-filament ironing temperature. It is kept apart from
// IroningTemperature.cpp on purpose: that file holds the config-def extension,
// which PrintConfig.cpp pulls into every program linking libslic3r. Calling the
// G-code generator from there would drag GCode.o (and the 3MF/SVG code that needs
// nanosvg) into small tools such as generate_system_cache, which then fail to link.
#include "IroningTemperature.hpp"

#include <algorithm>

#include "libslic3r/Config.hpp"
#include "libslic3r/GCode.hpp"
#include "libslic3r/GCodeWriter.hpp"
#include "libslic3r/PrintConfig.hpp"

namespace Slic3r {
namespace Cosmyx {

namespace {

// Print temperature of filament_id, as GCode::set_extruder() picks it: the first layer
// temperature on the first layer, the normal one elsewhere. Each falls back on the other
// when it is 0, and 0 is returned when both are, so the caller never turns the heater off.
int print_temperature(const GCode& gcodegen, unsigned int filament_id, bool first_layer)
{
    // Nozzle temperatures are variant-expanded, so they use the filament's config column.
    const size_t fi = gcodegen.get_filament_config_index(int(filament_id));
    const int initial = gcodegen.config().nozzle_temperature_initial_layer.get_at(fi);
    const int normal = gcodegen.config().nozzle_temperature.get_at(fi);
    const int temperature = first_layer ? initial : normal;
    return temperature > 0 ? temperature : std::max(0, first_layer ? normal : initial);
}

std::string set_temperature(const GCode& gcodegen, int temperature, unsigned int filament_id)
{
    if (temperature <= 0)
        return std::string();
    return gcodegen.writer().set_temperature(unsigned(temperature), false, int(filament_id));
}

} // namespace

std::string ironing_temperature_gcode(const GCode& gcodegen, const DynamicPrintConfig& full, ExtrusionRole from,
                                      ExtrusionRole to, bool first_layer)
{
    const Extruder* filament = gcodegen.writer().filament();
    if (filament == nullptr || from == to)
        return std::string();
    const unsigned int id = filament->id();

    if (to == erIroning)
        return set_temperature(gcodegen, ironing_temperature(full, id), id);

    // Leaving ironing. After a tool change the last ironing path may belong to another
    // filament, whose ironing temperature this one may not share: on a single nozzle the
    // heater is still at that temperature. So restore whenever any filament irons at its own
    // temperature; on a multi-tool printer that costs at most one redundant command.
    if (from == erIroning && any_ironing_temperature(full))
        return set_temperature(gcodegen, print_temperature(gcodegen, id, first_layer), id);

    return std::string();
}

std::string ironing_temperature_toolchange_gcode(const GCode& gcodegen, const DynamicPrintConfig& full,
                                                 ExtrusionRole last_role, bool first_layer)
{
    const Extruder* filament = gcodegen.writer().filament();
    if (filament == nullptr || last_role != erIroning)
        return std::string();
    const unsigned int id = filament->id();
    if (ironing_temperature(full, id) <= 0)
        return std::string();
    return set_temperature(gcodegen, print_temperature(gcodegen, id, first_layer), id);
}

} // namespace Cosmyx
} // namespace Slic3r
