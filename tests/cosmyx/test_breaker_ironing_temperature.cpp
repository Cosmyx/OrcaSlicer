// Breaker tests for the Cosmyx ironing temperature (filament_ironing_temperature).
//
// The option declares the range [0, 500] (IroningTemperature.cpp,
// extend_ironing_temperature()). Every other numeric print option with a range
// is checked by DynamicPrintConfig::validate(), which the GUI and the CLI run
// before slicing. That check copies the dynamic config into a static
// FullPrintConfig (fpc.apply(*this, true)) and only walks the static keys.
// filament_ironing_temperature is not a FullPrintConfig member (it is added
// through Cosmyx::add_option()), so it is dropped by that copy and its range is
// never checked: a profile, 3MF project or CLI config holding 600 validates
// cleanly and the G-code then sets the nozzle to M104 S600 while ironing.

#include <catch2/catch_test_macros.hpp>

#include <map>
#include <string>

#include "libslic3r/Config.hpp"
#include "libslic3r/PrintConfig.hpp"

using namespace Slic3r;

namespace {

const std::string key = "filament_ironing_temperature";

} // namespace

TEST_CASE("Config validation refuses an ironing temperature above its maximum", "[cosmyx][breaker][IroningTemperature]")
{
    const ConfigOptionDef* def = print_config_def.get(key);
    REQUIRE(def != nullptr);
    REQUIRE(int(def->max) == 500);

    DynamicPrintConfig config = DynamicPrintConfig::full_print_config();
    config.set_deserialize_strict(key, "600");
    const std::map<std::string, std::string> errors = config.validate();
    // Expected: "600 not in range [0, 500]", as for any upstream option.
    // Actual: no entry, because validate() never sees the Cosmyx option.
    CHECK(errors.count(key) == 1);
}

TEST_CASE("Config validation refuses a negative ironing temperature", "[cosmyx][breaker][IroningTemperature]")
{
    DynamicPrintConfig config = DynamicPrintConfig::full_print_config();
    config.set_deserialize_strict(key, "0,-5");
    const std::map<std::string, std::string> errors = config.validate();
    CHECK(errors.count(key) == 1);
}

TEST_CASE("Config validation accepts ironing temperatures inside the range", "[cosmyx][breaker][IroningTemperature]")
{
    // Guards the two tests above: the bounds themselves stay valid.
    DynamicPrintConfig config = DynamicPrintConfig::full_print_config();
    config.set_deserialize_strict(key, "0,500");
    const std::map<std::string, std::string> errors = config.validate();
    CHECK(errors.count(key) == 0);
}
