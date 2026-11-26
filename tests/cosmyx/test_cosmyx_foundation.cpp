// Checks of the Cosmyx foundation: the PrintConfigDef seam, the add_option()
// helper and the invariants every Cosmyx option must keep.

#include <catch2/catch_test_macros.hpp>

#include <cmath>
#include <stdexcept>
#include <string>
#include <vector>

#include "libslic3r/Config.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "libslic3r/Cosmyx/ConfigDefExtensions.hpp"

using namespace Slic3r;

namespace {

// Numeric values of an option's default, nil entries left out. Empty for an
// option whose type has no numeric range.
std::vector<double> numeric_defaults(const ConfigOption& value)
{
    std::vector<double> out;
    if (value.is_scalar()) {
        if (value.is_nil())
            return out;
        switch (value.type()) {
        case coFloat:
        case coPercent:
        case coFloatOrPercent: out.push_back(value.getFloat()); break;
        case coInt: out.push_back(double(value.getInt())); break;
        default: break;
        }
        return out;
    }
    const auto* vec = dynamic_cast<const ConfigOptionVectorBase*>(&value);
    if (vec == nullptr)
        return out;
    if (const auto* floats = dynamic_cast<const ConfigOptionVector<double>*>(&value)) {
        for (size_t i = 0; i < floats->values.size(); ++i)
            if (!vec->is_nil(i))
                out.push_back(floats->values[i]);
    } else if (const auto* ints = dynamic_cast<const ConfigOptionVector<int>*>(&value)) {
        for (size_t i = 0; i < ints->values.size(); ++i)
            if (!vec->is_nil(i))
                out.push_back(double(ints->values[i]));
    }
    return out;
}

} // namespace

TEST_CASE("PrintConfigDef runs the Cosmyx dispatcher", "[cosmyx]")
{
    // Touching print_config_def guarantees the global definition is built.
    REQUIRE(print_config_def.has("nozzle_type"));
    CHECK(Cosmyx::extend_print_config_def_calls() >= 1);
}

TEST_CASE("Every Cosmyx extender can run on a definition", "[cosmyx]")
{
    // Linking these calls proves each feature file defines its extender. The
    // extenders run on a fresh definition, which already went through the
    // dispatcher in its constructor, so the extenders' option keys are taken
    // out first; running them again must then succeed.
    PrintConfigDef def;
    const size_t calls_before = Cosmyx::extend_print_config_def_calls();
    std::vector<std::string> cosmyx_keys;
    for (const auto& [key, opt] : def.options)
        if (Cosmyx::is_cosmyx_option(opt))
            cosmyx_keys.push_back(key);
    for (const std::string& key : cosmyx_keys) {
        def.by_serialization_key_ordinal.erase(def.options[key].serialization_key_ordinal);
        def.options.erase(key);
    }

    CHECK_NOTHROW(Cosmyx::extend_bed_temperature_off(def));
    CHECK_NOTHROW(Cosmyx::extend_cht_nozzle(def));
    CHECK_NOTHROW(Cosmyx::extend_ironing_temperature(def));
    CHECK(Cosmyx::extend_print_config_def_calls() == calls_before);

    for (const std::string& key : cosmyx_keys)
        CHECK(def.has(key));
}

TEST_CASE("add_option registers a Cosmyx option", "[cosmyx]")
{
    PrintConfigDef def;
    const std::string key = "cosmyx_foundation_test_option";
    REQUIRE_FALSE(def.has(key));

    ConfigOptionDef* opt = Cosmyx::add_option(def, key, coFloat);
    REQUIRE(opt != nullptr);
    CHECK(opt->opt_key == key);
    CHECK(opt->type == coFloat);
    CHECK_FALSE(opt->nullable);
    CHECK(Cosmyx::is_cosmyx_option(*opt));
    CHECK(def.get(key) == opt);

    // The ordinal resolves back to the option, as undo/redo serialization needs.
    const auto it = def.by_serialization_key_ordinal.find(opt->serialization_key_ordinal);
    REQUIRE(it != def.by_serialization_key_ordinal.end());
    CHECK(it->second == opt);

    SECTION("a second option gets another ordinal")
    {
        ConfigOptionDef* other = Cosmyx::add_option(def, key + "_nullable", coInts, true);
        CHECK(other->nullable);
        CHECK(other->serialization_key_ordinal != opt->serialization_key_ordinal);
    }

    SECTION("a key that already exists is refused")
    {
        CHECK_THROWS_AS(Cosmyx::add_option(def, key, coFloat), std::logic_error);
        CHECK_THROWS_AS(Cosmyx::add_option(def, "nozzle_type", coEnums), std::logic_error);
    }
}

TEST_CASE("Upstream options keep their upstream ordinals", "[cosmyx]")
{
    REQUIRE(print_config_def.has("nozzle_type"));
    CHECK_FALSE(Cosmyx::is_cosmyx_option(*print_config_def.get("nozzle_type")));
}

TEST_CASE("Every Cosmyx option default is within its own range", "[cosmyx]")
{
    REQUIRE_FALSE(print_config_def.options.empty());
    for (const auto& [key, opt] : print_config_def.options) {
        if (!Cosmyx::is_cosmyx_option(opt))
            continue;
        INFO("option " << key);
        REQUIRE(opt.default_value);
        CHECK(opt.printer_technology == ptFFF);
        for (double value : numeric_defaults(*opt.default_value)) {
            CHECK(value >= double(opt.min));
            CHECK(value <= double(opt.max));
        }
    }
}
