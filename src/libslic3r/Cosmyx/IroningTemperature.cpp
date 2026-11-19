#include "ConfigDefExtensions.hpp"
#include "IroningTemperature.hpp"

#include <algorithm>

#include "libslic3r/Config.hpp"
#include "libslic3r/GCode.hpp"
#include "libslic3r/GCodeWriter.hpp"
#include "libslic3r/I18N.hpp"
#include "libslic3r/PrintConfig.hpp"

namespace Slic3r {
namespace Cosmyx {

const char* const ironing_temperature_key = "filament_ironing_temperature";

void extend_ironing_temperature(PrintConfigDef& def)
{
    ConfigOptionDef* opt = add_option(def, ironing_temperature_key, coInts);
    opt->label = L("Ironing temperature");
    opt->full_label = L("Ironing temperature");
    opt->tooltip = L("Nozzle temperature while this filament irons. The nozzle goes back to the print "
                     "temperature once ironing is done. 0 means no change.");
    opt->sidetext = L(u8"\u2103" /* degrees Celsius */);
    opt->min = 0;
    opt->max = 500;
    opt->mode = comAdvanced;
    opt->set_default_value(new ConfigOptionInts{0});
}

int ironing_temperature(const DynamicPrintConfig& full, unsigned int filament_id)
{
    const auto* opt = full.option<ConfigOptionInts>(ironing_temperature_key);
    if (opt == nullptr || opt->values.empty())
        return 0;
    return std::max(0, opt->get_at(filament_id));
}

bool any_ironing_temperature(const DynamicPrintConfig& full)
{
    const auto* opt = full.option<ConfigOptionInts>(ironing_temperature_key);
    return opt != nullptr && std::any_of(opt->values.begin(), opt->values.end(), [](int t) { return t > 0; });
}

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
