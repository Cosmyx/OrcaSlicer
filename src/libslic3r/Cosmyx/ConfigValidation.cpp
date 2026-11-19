#include "ConfigDefExtensions.hpp"

#include <cstddef>
#include <map>
#include <string>

#include "libslic3r/Config.hpp"
#include "libslic3r/I18N.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "libslic3r/format.hpp"

namespace Slic3r {
namespace Cosmyx {

namespace {

// True when a value of the vector opt, nil values aside, is outside the range of optdef.
template<typename T> bool vector_out_of_range(const ConfigOption& opt, const ConfigOptionDef& optdef)
{
    const auto& vec = static_cast<const ConfigOptionVector<T>&>(opt);
    for (std::size_t i = 0; i < vec.values.size(); ++i)
        if (!vec.is_nil(i) && !optdef.is_value_valid(double(vec.values[i])))
            return true;
    return false;
}

// True when opt holds a value outside the range of optdef. The same numeric types as the
// out of range check of Slic3r::validate(); the other types have no range.
bool out_of_range(const ConfigOption& opt, const ConfigOptionDef& optdef)
{
    switch (opt.type()) {
    case coFloat:
    case coPercent:
    case coFloatOrPercent: return !optdef.is_value_valid(static_cast<const ConfigOptionSingle<double>&>(opt).value);
    case coFloats:
    case coPercents: return vector_out_of_range<double>(opt, optdef);
    case coInt: return !optdef.is_value_valid(double(static_cast<const ConfigOptionSingle<int>&>(opt).value));
    case coInts: return vector_out_of_range<int>(opt, optdef);
    default: return false;
    }
}

} // namespace

std::map<std::string, std::string> validate_option_ranges(const DynamicPrintConfig& config, std::map<std::string, std::string> errors)
{
    for (const std::string& opt_key : config.keys()) {
        const ConfigOptionDef* optdef = print_config_def.get(opt_key);
        if (optdef == nullptr || !is_cosmyx_option(*optdef))
            continue;
        const ConfigOption* opt = config.option(opt_key);
        if (opt == nullptr || errors.count(opt_key) != 0 || !out_of_range(*opt, *optdef))
            continue;
        // The message of Slic3r::validate(), so it shares its translation.
        // TRN %1% is the current value, %2% and %3% the lowest and highest allowed values.
        errors.emplace(opt_key, Slic3r::format(_u8L("%1% not in range [%2%, %3%]"), opt->serialize(), optdef->min, optdef->max));
    }
    return errors;
}

} // namespace Cosmyx
} // namespace Slic3r
