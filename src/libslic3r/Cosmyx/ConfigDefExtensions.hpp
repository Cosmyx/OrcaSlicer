#ifndef slic3r_Cosmyx_ConfigDefExtensions_hpp_
#define slic3r_Cosmyx_ConfigDefExtensions_hpp_

// Seam between PrintConfigDef and the Cosmyx print options.
//
// PrintConfigDef::PrintConfigDef() calls extend_print_config_def() once, after
// the FFF options are defined and before they are tagged ptFFF, so every Cosmyx
// option is an FFF option like its upstream neighbours. Each feature owns one
// extender, defined in its own source file, so features never edit the same
// lines.

#include <cstddef>
#include <map>
#include <string>

#include "libslic3r/Config.hpp"

namespace Slic3r {

class DynamicPrintConfig;
class PrintConfigDef;

namespace Cosmyx {

// First serialization ordinal handed out by add_option(). ConfigDef::add()
// numbers upstream options from 1 with one counter shared by every ConfigDef;
// Cosmyx options use a range far above it so the two never collide, whatever
// the number of upstream options.
constexpr std::size_t option_ordinal_base = std::size_t(1) << 30;

// Defines a new option on def. ConfigDef::add() is protected, so Cosmyx code
// goes through this helper instead. It fills the same fields as ConfigDef::add()
// (key, type, a unique serialization ordinal registered in
// by_serialization_key_ordinal) and sets nullable on request.
// Throws std::logic_error if the key already exists, so a clash with an
// upstream option fails loudly at startup instead of overwriting it.
ConfigOptionDef* add_option(PrintConfigDef& def, const std::string& key, ConfigOptionType type, bool nullable = false);

// True for an option defined through add_option().
bool is_cosmyx_option(const ConfigOptionDef& opt);

// Out of range check of the Cosmyx options of config. Slic3r::validate() only walks
// the static FullPrintConfig, which holds no Cosmyx option, so
// DynamicPrintConfig::validate() passes its result through here. For each Cosmyx
// option of config with a numeric value outside its [min, max], and no entry yet
// in errors, adds the same "not in range" message as Slic3r::validate(). Returns
// errors with those entries added.
std::map<std::string, std::string> validate_option_ranges(const DynamicPrintConfig& config, std::map<std::string, std::string> errors);

// Runs every Cosmyx extender on def. Called from PrintConfigDef::PrintConfigDef().
void extend_print_config_def(PrintConfigDef& def);

// Number of times extend_print_config_def() has run in this process. Lets the
// tests check that the PrintConfigDef hook is in place.
std::size_t extend_print_config_def_calls();

// One extender per feature, each defined in the feature's own source file.
void extend_bed_temperature_off(PrintConfigDef& def);

void extend_cht_nozzle(PrintConfigDef& def);

void extend_ironing_temperature(PrintConfigDef& def);

} // namespace Cosmyx
} // namespace Slic3r

#endif // slic3r_Cosmyx_ConfigDefExtensions_hpp_
