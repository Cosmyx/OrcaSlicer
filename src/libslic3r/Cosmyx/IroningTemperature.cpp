#include "ConfigDefExtensions.hpp"
#include "IroningTemperature.hpp"

#include <algorithm>

#include "libslic3r/Config.hpp"
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

} // namespace Cosmyx
} // namespace Slic3r
