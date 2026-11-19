#include "ConfigDefExtensions.hpp"
#include "BedTemperatureOff.hpp"

#include <algorithm>

#include "libslic3r/Config.hpp"
#include "libslic3r/PlaceholderParser.hpp"
#include "libslic3r/PrintConfig.hpp"

namespace Slic3r {
namespace Cosmyx {

namespace {

bool ends_with(const std::string& text, const std::string& suffix)
{
    return text.size() >= suffix.size() && text.compare(text.size() - suffix.size(), suffix.size(), suffix) == 0;
}

} // namespace

bool is_bed_temperature_key(const std::string& key)
{
    return ends_with(key, "_plate_temp") || ends_with(key, "_plate_temp_initial_layer");
}

void extend_bed_temperature_off(PrintConfigDef& def)
{
    // Matched by pattern rather than by a list, so a plate type added upstream
    // accepts -1 too without a Cosmyx change. Tooltips stay upstream's
    // (decision 0011).
    for (auto& [key, opt] : def.options)
        if (opt.type == coInts && is_bed_temperature_key(key))
            opt.min = float(bed_temperature_off);
}

void clamp_bed_temperature_placeholders(PlaceholderParser& parser)
{
    DynamicConfig& config = parser.config_writable();

    for (const char* key : {"bed_temperature", "bed_temperature_initial_layer", "first_layer_bed_temperature"})
        if (ConfigOptionInts* opt = config.option<ConfigOptionInts>(key))
            for (int& value : opt->values)
                value = std::max(value, 0);

    if (ConfigOptionInt* opt = config.option<ConfigOptionInt>("bed_temperature_initial_layer_single"))
        opt->value = std::max(opt->value, 0);
}

} // namespace Cosmyx
} // namespace Slic3r
