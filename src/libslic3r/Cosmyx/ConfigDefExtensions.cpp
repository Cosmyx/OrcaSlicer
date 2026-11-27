#include "ConfigDefExtensions.hpp"

#include <atomic>
#include <stdexcept>

#include "libslic3r/PrintConfig.hpp"

namespace Slic3r {
namespace Cosmyx {

namespace {

std::atomic<std::size_t> s_extend_calls{0};

} // namespace

ConfigOptionDef* add_option(PrintConfigDef& def, const std::string& key, ConfigOptionType type, bool nullable)
{
    // Ordinals are unique across every ConfigDef, as ConfigDef::add() keeps
    // them, because PrintAndCLIConfigDef merges several defs by ordinal.
    static std::atomic<std::size_t> s_last_ordinal{option_ordinal_base};

    if (def.options.count(key) != 0)
        throw std::logic_error("Cosmyx::add_option: option \"" + key + "\" is already defined");

    ConfigOptionDef* opt = &def.options[key];
    opt->opt_key = key;
    opt->type = type;
    opt->nullable = nullable;
    opt->serialization_key_ordinal = ++s_last_ordinal;
    def.by_serialization_key_ordinal[opt->serialization_key_ordinal] = opt;
    return opt;
}

bool is_cosmyx_option(const ConfigOptionDef& opt)
{
    return opt.serialization_key_ordinal > option_ordinal_base;
}

std::size_t extend_print_config_def_calls()
{
    return s_extend_calls.load();
}

void extend_print_config_def(PrintConfigDef& def)
{
    ++s_extend_calls;

    extend_bed_temperature_off(def);

    extend_cht_nozzle(def);

    extend_ironing_temperature(def);
}

} // namespace Cosmyx
} // namespace Slic3r
