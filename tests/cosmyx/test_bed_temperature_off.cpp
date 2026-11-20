// Checks of the Cosmyx BedTemperatureOff feature: a bed temperature of -1
// turns the bed heater off (M140 S0, never M190), while 0 keeps its upstream
// meaning "the filament does not support this plate".

#include <catch2/catch_test_macros.hpp>
#include <catch2/catch_tostring.hpp>
#include <catch2/generators/catch_generators.hpp>

#include <map>
#include <sstream>
#include <string>
#include <vector>

#include "libslic3r/Config.hpp"
#include "libslic3r/GCodeWriter.hpp"
#include "libslic3r/Model.hpp"
#include "libslic3r/Print.hpp"
#include "libslic3r/PrintBase.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "libslic3r/Cosmyx/BedTemperatureOff.hpp"

#include "test_helpers.hpp"

using namespace Slic3r;

namespace {

const std::vector<std::string> bed_temperature_keys = {
    "supertack_plate_temp",
    "cool_plate_temp",
    "textured_cool_plate_temp",
    "eng_plate_temp",
    "hot_plate_temp",
    "textured_plate_temp",
    "supertack_plate_temp_initial_layer",
    "cool_plate_temp_initial_layer",
    "textured_cool_plate_temp_initial_layer",
    "eng_plate_temp_initial_layer",
    "hot_plate_temp_initial_layer",
    "textured_plate_temp_initial_layer",
};

// Full print config with every plate's bed temperature set to value, first
// layer and other layers alike, so the test does not depend on the bed type.
DynamicPrintConfig config_with_bed_temperature(int value)
{
    DynamicPrintConfig config = DynamicPrintConfig::full_print_config();
    for (const std::string& key : bed_temperature_keys)
        config.set_deserialize_strict(key, std::to_string(value));
    config.set_deserialize_strict({{"skirt_loops", "0"}, {"brim_type", "no_brim"}});
    return config;
}

// Every M140 / M190 line of gcode, as written.
std::vector<std::string> bed_temperature_lines(const std::string& gcode)
{
    std::vector<std::string> out;
    std::istringstream lines(gcode);
    for (std::string line; std::getline(lines, line);)
        if (line.rfind("M140", 0) == 0 || line.rfind("M190", 0) == 0)
            out.push_back(line);
    return out;
}

// Value written after "<tag> " on a start G-code comment line.
int tagged_value(const std::string& gcode, const std::string& tag)
{
    const std::string token = "\n;" + tag + " ";
    const size_t pos = gcode.find(token);
    REQUIRE(pos != std::string::npos);
    return std::stoi(gcode.substr(pos + token.size()));
}

// Start G-code that prints the bed temperature placeholders on comment lines,
// which the slicer does not read as temperature commands.
const char* placeholder_start_gcode =
    "G28\n"
    ";COSMYX_SINGLE {bed_temperature_initial_layer_single}\n"
    ";COSMYX_INITIAL {bed_temperature_initial_layer[0]}\n"
    ";COSMYX_OTHER {bed_temperature[0]}\n"
    ";COSMYX_FIRST {first_layer_bed_temperature[0]}\n"
    ";COSMYX_RAW {cool_plate_temp_initial_layer[0]}\n";

} // namespace

TEST_CASE("Bed temperature keys are recognised by pattern", "[cosmyx][BedTemperatureOff]")
{
    for (const std::string& key : bed_temperature_keys)
        CHECK(Cosmyx::is_bed_temperature_key(key));
    CHECK_FALSE(Cosmyx::is_bed_temperature_key("nozzle_temperature"));
    CHECK_FALSE(Cosmyx::is_bed_temperature_key("chamber_temperature"));
    CHECK_FALSE(Cosmyx::is_bed_temperature_key("hot_plate_temp_extra"));
}

TEST_CASE("Every plate bed temperature accepts -1", "[cosmyx][BedTemperatureOff]")
{
    for (const std::string& key : bed_temperature_keys) {
        INFO("option " << key);
        const ConfigOptionDef* def = print_config_def.get(key);
        REQUIRE(def != nullptr);
        CHECK(def->type == coInts);
        CHECK(int(def->min) == Cosmyx::bed_temperature_off);
        CHECK(def->is_value_valid(-1));
        CHECK(def->is_value_valid(0));
        CHECK_FALSE(def->is_value_valid(-2));
        // Decision 0011: the upstream tooltip, which explains 0, is kept.
        CHECK(def->tooltip.find("A value of 0 means") != std::string::npos);
    }

    // Any other option the pattern matches gets the same bound.
    for (const auto& [key, def] : print_config_def.options)
        if (def.type == coInts && Cosmyx::is_bed_temperature_key(key)) {
            INFO("option " << key);
            CHECK(int(def.min) == Cosmyx::bed_temperature_off);
        }
}

TEST_CASE("Config validation accepts -1 and refuses -2 as a bed temperature", "[cosmyx][BedTemperatureOff]")
{
    DynamicPrintConfig config = DynamicPrintConfig::full_print_config();
    config.set_deserialize_strict("hot_plate_temp", "-1");
    config.set_deserialize_strict("cool_plate_temp_initial_layer", "-2");
    const std::map<std::string, std::string> errors = config.validate();
    CHECK(errors.count("hot_plate_temp") == 0);
    CHECK(errors.count("cool_plate_temp_initial_layer") == 1);
}

TEST_CASE("The G-code writer turns the bed off for -1 and never waits", "[cosmyx][BedTemperatureOff]")
{
    GCodeWriter writer;

    SECTION("on a fresh writer")
    {
        CHECK(writer.set_bed_temperature(-1, true).rfind("M140 S0 ", 0) == 0);
        // Already off: nothing more to write.
        CHECK(writer.set_bed_temperature(-1, true).empty());
        CHECK(writer.set_bed_temperature(-1, false).empty());
    }

    SECTION("after the bed was heated and reached")
    {
        CHECK(writer.set_bed_temperature(60, true).rfind("M190 S60 ", 0) == 0);
        CHECK(writer.set_bed_temperature(-1, true).rfind("M140 S0 ", 0) == 0);
    }

    SECTION("after the bed was heated without waiting")
    {
        CHECK(writer.set_bed_temperature(60, false).rfind("M140 S60 ", 0) == 0);
        CHECK(writer.set_bed_temperature(-1, true).rfind("M140 S0 ", 0) == 0);
    }

    SECTION("0 keeps its upstream behaviour")
    {
        // Fresh writer: the bed is assumed at 0 already, as upstream does.
        CHECK(writer.set_bed_temperature(0, true).empty());
        CHECK(writer.set_bed_temperature(60, true).rfind("M190 S60 ", 0) == 0);
        CHECK(writer.set_bed_temperature(0, true).rfind("M190 S0 ", 0) == 0);
    }
}

TEST_CASE("A print with the bed off never writes a negative or waited bed temperature", "[cosmyx][BedTemperatureOff]")
{
    DynamicPrintConfig config = config_with_bed_temperature(Cosmyx::bed_temperature_off);
    config.set_deserialize_strict("bed_temperature_formula", "by_first_filament");
    const std::string gcode = Test::slice({Test::cube(20)}, config);

    const std::vector<std::string> lines = bed_temperature_lines(gcode);
    INFO("bed temperature lines: " << Catch::Detail::stringify(lines));
    REQUIRE_FALSE(lines.empty());
    CHECK(lines.front().rfind("M140 S0 ", 0) == 0);
    for (const std::string& line : lines) {
        CHECK(line.rfind("M190", 0) != 0);
        CHECK(line.find("S-") == std::string::npos);
    }
}

TEST_CASE("Bed temperature placeholders read 0 when the bed is off", "[cosmyx][BedTemperatureOff]")
{
    const std::string formula = GENERATE("by_first_filament", "by_highest_temp");
    DYNAMIC_SECTION("bed_temperature_formula " << formula)
    {
        DynamicPrintConfig config = config_with_bed_temperature(Cosmyx::bed_temperature_off);
        config.set_deserialize_strict("bed_temperature_formula", formula);
        config.set_deserialize_strict("machine_start_gcode", placeholder_start_gcode);
        const std::string gcode = Test::slice({Test::cube(20)}, config);

        CHECK(tagged_value(gcode, "COSMYX_SINGLE") == 0);
        CHECK(tagged_value(gcode, "COSMYX_INITIAL") == 0);
        CHECK(tagged_value(gcode, "COSMYX_OTHER") == 0);
        CHECK(tagged_value(gcode, "COSMYX_FIRST") == 0);
        // Decision 0012: the raw plate keys keep the configured -1.
        CHECK(tagged_value(gcode, "COSMYX_RAW") == -1);

        for (const std::string& line : bed_temperature_lines(gcode)) {
            INFO("line " << line);
            CHECK(line.rfind("M190", 0) != 0);
            CHECK(line.find("S-") == std::string::npos);
        }
    }
}

TEST_CASE("Bed temperature placeholders keep positive values", "[cosmyx][BedTemperatureOff]")
{
    DynamicPrintConfig config = config_with_bed_temperature(55);
    config.set_deserialize_strict("machine_start_gcode", placeholder_start_gcode);
    const std::string gcode = Test::slice({Test::cube(20)}, config);

    CHECK(tagged_value(gcode, "COSMYX_SINGLE") == 55);
    CHECK(tagged_value(gcode, "COSMYX_FIRST") == 55);
    CHECK(tagged_value(gcode, "COSMYX_OTHER") == 55);
}

TEST_CASE("A bed temperature of 0 still means the filament does not support the plate", "[cosmyx][BedTemperatureOff]")
{
    // validate() returns its first error, so the config must pass every check
    // before the bed type one. The default Marlin flavour with relative E needs
    // "G92 E0" in the layer change G-code, or validate() stops there first.
    const auto validate_with = [](int value) {
        DynamicPrintConfig config = config_with_bed_temperature(value);
        config.set_deserialize_strict({{"support_multi_bed_types", "1"}, {"layer_change_gcode", "G92 E0\n"}});
        Print print;
        Model model;
        Test::init_print({Test::cube(20)}, print, model, config);
        return print.validate();
    };

    SECTION("0 refuses the plate")
    {
        const StringObjectException error = validate_with(0);
        INFO("validate(): " << error.string);
        CHECK(error.type == STRING_EXCEPT_FILAMENT_NOT_MATCH_BED_TYPE);
        CHECK(error.string.find("does not support filament 1") != std::string::npos);
    }

    SECTION("-1 and a positive value pass the whole validation")
    {
        const int value = GENERATE(Cosmyx::bed_temperature_off, 60);
        const StringObjectException error = validate_with(value);
        INFO("bed temperature " << value << ", validate(): " << error.string);
        CHECK(error.type != STRING_EXCEPT_FILAMENT_NOT_MATCH_BED_TYPE);
        CHECK(error.string.empty());
    }
}
