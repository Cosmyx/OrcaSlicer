// Checks of the Cosmyx ironing temperature: the filament_ironing_temperature option and the
// nozzle temperature commands it adds around ironing, on one tool and on two.

#include <catch2/catch_test_macros.hpp>
#include <catch2/generators/catch_generators.hpp>

#include <algorithm>
#include <cctype>
#include <map>
#include <set>
#include <string>
#include <vector>

#include "libslic3r/Config.hpp"
#include "libslic3r/GCodeReader.hpp"
#include "libslic3r/Preset.hpp"
#include "libslic3r/PresetBundle.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "libslic3r/Cosmyx/ConfigDefExtensions.hpp"
#include "libslic3r/Cosmyx/IroningTemperature.hpp"

#include "test_helpers.hpp"

using namespace Slic3r;

namespace {

const std::string key = "filament_ironing_temperature";

// What a printer would do with the G-code: the target temperature of each tool, the tool
// in use, the feature being printed and the layer, replayed line by line.
struct ToolTemperatures
{
    std::map<int, int> target;
    int                tool = 0;
    std::string        type;
    int                layer = -1;
};

// Calls on_extrusion(state) before every extruding move that lays down material, with the
// temperature commands seen so far applied.
template<typename Fn> void replay(const std::string& gcode, Fn&& on_extrusion)
{
    ToolTemperatures state;
    GCodeReader      reader;
    reader.parse_buffer(gcode, [&](GCodeReader& self, const GCodeReader::GCodeLine& line) {
        const std::string& raw = line.raw();
        if (raw.rfind(";TYPE:", 0) == 0) {
            state.type = raw.substr(6);
            return;
        }
        if (raw.rfind(";LAYER_CHANGE", 0) == 0) {
            ++state.layer;
            return;
        }
        const std::string cmd(line.cmd());
        if (cmd.size() >= 2 && cmd[0] == 'T' && std::all_of(cmd.begin() + 1, cmd.end(), [](char c) { return std::isdigit((unsigned char) c) != 0; })) {
            state.tool = std::stoi(cmd.substr(1));
            return;
        }
        if (cmd == "M104" || cmd == "M109") {
            float s = 0.f, t = 0.f;
            if (line.has_value('S', s))
                state.target[line.has_value('T', t) ? int(t) : state.tool] = int(s);
            return;
        }
        if (line.extruding(self) && line.dist_XY(self) > EPSILON)
            on_extrusion(state);
    });
}

// One tool on every layer, with a first layer temperature of its own.
DynamicPrintConfig one_tool_config(int ironing_temperature, int first_layer, int other_layers)
{
    DynamicPrintConfig config = DynamicPrintConfig::full_print_config();
    config.set_deserialize_strict({
        {"nozzle_temperature_initial_layer", first_layer},
        {"nozzle_temperature", other_layers},
        {key, ironing_temperature},
        // Every solid layer is ironed, so ironing is followed by more printing.
        {"ironing_type", "solid"},
        {"skirt_loops", 0},
        {"brim_type", "no_brim"},
        // Without the end G-code's heater-off command, every temperature command is the
        // slicer's own.
        {"machine_end_gcode", ""},
        {"preheat_time", 0},
    });
    return config;
}

// Two tools on two nozzles, filament 1 ironing at 190 and filament 2 at second_ironing,
// with or without a prime tower.
DynamicPrintConfig two_tool_config(bool prime_tower, int second_ironing)
{
    DynamicPrintConfig config = Test::multifilament_config(2, {
        {"nozzle_diameter", "0.4,0.4"},
        {"printer_extruder_id", "1,2"},
        {"printer_extruder_variant", "Direct Drive Standard,Direct Drive Standard"},
        {"extruder_printable_height", "0,0"},
        {"filament_self_index", "1,2"},
        {"single_extruder_multi_material", 0},
        {"enable_prime_tower", prime_tower ? 1 : 0},
        {"prime_tower_width", 35},
        {"wipe_tower_x", "50"},
        {"wipe_tower_y", "50"},
        {"nozzle_temperature_initial_layer", "225,235"},
        {"nozzle_temperature", "220,230"},
        {key, "190," + std::to_string(second_ironing)},
        {"skirt_loops", 0},
        {"brim_type", "no_brim"},
        {"machine_end_gcode", ""},
        // The preheat pass would raise the incoming tool on its own and hide a tool left
        // at the ironing temperature.
        {"preheat_time", 0},
    });
    Test::size_flush_to_nozzles(config);
    return config;
}

// One filament per object, so both tools print on every layer. Every solid layer is ironed,
// so each tool comes back after ironing on the layers above.
std::string slice_two_tools(const DynamicPrintConfig& config)
{
    return Test::slice_with_object_overrides(
        {Test::cube(20), Test::cube(20)}, config,
        {{{"extruder", "1"}, {"ironing_type", "solid"}}, {{"extruder", "2"}, {"ironing_type", "solid"}}});
}

} // namespace

TEST_CASE("filament_ironing_temperature is a filament option, off by default", "[cosmyx]")
{
    const ConfigOptionDef* opt = print_config_def.get(key);
    REQUIRE(opt != nullptr);
    CHECK(Cosmyx::is_cosmyx_option(*opt));
    CHECK(opt->type == coInts);
    CHECK_FALSE(opt->nullable);
    CHECK(opt->mode == comAdvanced);
    CHECK(opt->label == "Ironing temperature");
    CHECK(opt->min == 0);
    CHECK(opt->max == 500);
    REQUIRE(opt->default_value);
    CHECK(opt->default_value->serialize() == "0");

    const auto& filament_options = Preset::filament_options();
    CHECK(std::find(filament_options.begin(), filament_options.end(), key) != filament_options.end());
    // One value per filament, never one per extruder variant.
    CHECK(filament_options_with_variant.count(key) == 0);

    // The default filament preset stores it, at 0. PresetBundle::full_fff_config() applies
    // that preset over FullPrintConfig defaults, so the full config of every print carries
    // the option. DynamicPrintConfig::full_print_config() alone does not: it only holds the
    // static FullPrintConfig keys, and the option is not one of them.
    const PresetBundle bundle;
    const DynamicPrintConfig& filament_defaults = bundle.filaments.default_preset().config;
    REQUIRE(filament_defaults.has(key));
    CHECK(filament_defaults.opt_serialize(key) == "0");
    DynamicPrintConfig full = DynamicPrintConfig::full_print_config();
    full.apply(filament_defaults);
    REQUIRE(full.has(key));
    CHECK(Cosmyx::ironing_temperature(full, 0) == 0);
    CHECK_FALSE(Cosmyx::any_ironing_temperature(full));
}

TEST_CASE("The ironing temperature is read per filament id", "[cosmyx]")
{
    DynamicPrintConfig config = DynamicPrintConfig::full_print_config();
    config.set_deserialize_strict(key, "0,185");
    CHECK(Cosmyx::ironing_temperature(config, 0) == 0);
    CHECK(Cosmyx::ironing_temperature(config, 1) == 185);
    CHECK(Cosmyx::any_ironing_temperature(config));

    DynamicPrintConfig without;
    CHECK(Cosmyx::ironing_temperature(without, 0) == 0);
    CHECK_FALSE(Cosmyx::any_ironing_temperature(without));
}

TEST_CASE("One tool irons at the ironing temperature and prints at the print temperature", "[cosmyx]")
{
    const std::string gcode = Test::slice({Test::cube(20)}, one_tool_config(190, 225, 220));

    int  ironing_moves = 0, moves_after_ironing = 0;
    bool ironed        = false;
    replay(gcode, [&](const ToolTemperatures& state) {
        INFO("layer " << state.layer << ", " << state.type);
        if (state.type == "Ironing") {
            ++ironing_moves;
            ironed = true;
            CHECK(state.target.at(state.tool) == 190);
        } else if (ironed) {
            ++moves_after_ironing;
            CHECK(state.target.at(state.tool) == (state.layer <= 0 ? 225 : 220));
        }
    });
    REQUIRE(ironing_moves > 0);
    // The solid bottom layers are ironed, so printing goes on after ironing.
    REQUIRE(moves_after_ironing > 0);
    CHECK(gcode.find("M104 S190") != std::string::npos);
}

TEST_CASE("An ironing temperature of 0 adds no temperature command", "[cosmyx]")
{
    // The same temperature on every layer: upstream sets none after the first layer change.
    const std::string gcode  = Test::slice({Test::cube(20)}, one_tool_config(0, 220, 220));
    const size_t      layers = gcode.find(";LAYER_CHANGE");
    REQUIRE(layers != std::string::npos);
    REQUIRE(gcode.find(";TYPE:Ironing", layers) != std::string::npos);
    CHECK(gcode.find("M104", layers) == std::string::npos);
    CHECK(gcode.find("M109", layers) == std::string::npos);
}

TEST_CASE("A tool selected again after ironing prints at its print temperature", "[cosmyx]")
{
    const bool prime_tower = GENERATE(false, true);
    // Filament 2 irons at its print temperature, or at a temperature of its own.
    const int second_ironing = GENERATE(0, 180);
    DYNAMIC_SECTION("prime tower " << prime_tower << ", filament 2 ironing temperature " << second_ironing)
    {
        const DynamicPrintConfig config = two_tool_config(prime_tower, second_ironing);
        const std::string gcode = slice_two_tools(config);

        const std::map<int, int> ironing{{0, 190}, {1, second_ironing > 0 ? second_ironing : 230}};
        std::set<int>            ironed;
        std::map<int, int>       moves_after_ironing;
        std::set<int>            tools_seen;
        replay(gcode, [&](const ToolTemperatures& state) {
            INFO("layer " << state.layer << ", tool " << state.tool << ", " << state.type);
            tools_seen.insert(state.tool);
            const int first_layer = state.tool == 0 ? 225 : 235;
            const int other_layers = state.tool == 0 ? 220 : 230;
            if (state.type == "Ironing") {
                ironed.insert(state.tool);
                const int expected = (state.tool == 0 || second_ironing > 0) ? ironing.at(state.tool) :
                                                                               (state.layer <= 0 ? first_layer : other_layers);
                CHECK(state.target.at(state.tool) == expected);
            } else if (ironed.count(state.tool) != 0) {
                ++moves_after_ironing[state.tool];
                CHECK(state.target.at(state.tool) == (state.layer <= 0 ? first_layer : other_layers));
            }
        });
        REQUIRE(tools_seen == std::set<int>{0, 1});
        REQUIRE(ironed.count(0) == 1);
        REQUIRE(moves_after_ironing[0] > 0);
    }
}

TEST_CASE("A tool left after ironing is back at its print temperature before the tool change", "[cosmyx]")
{
    // With pre-heating on (multi-nozzle printers), the G-code processor anchors the
    // "Multi extruder pre cooling" M104 of the outgoing tool on the tool change itself: the
    // T or M1020 line, or the tower's NOZZLE_CHANGE_START / NOZZLE_CHANGE_END markers, and
    // inserts it after that line. The restore of a tool that ironed last therefore has to
    // come before the tool change, or it would undo the pre-cooling (decision 0036).
    const bool prime_tower = GENERATE(false, true);
    DYNAMIC_SECTION("prime tower " << prime_tower)
    {
        const std::string gcode = slice_two_tools(two_tool_config(prime_tower, 180));

        std::map<int, int>         target;
        std::map<int, std::string> last_model_type; // feature of each tool's last model extrusion
        int                        tool = 0, layer = -1, changes_after_ironing = 0;
        std::string                type;
        GCodeReader                reader;
        reader.parse_buffer(gcode, [&](GCodeReader& self, const GCodeReader::GCodeLine& line) {
            const std::string& raw = line.raw();
            if (raw.rfind(";TYPE:", 0) == 0) {
                type = raw.substr(6);
                return;
            }
            if (raw.rfind(";LAYER_CHANGE", 0) == 0) {
                ++layer;
                return;
            }
            const std::string cmd(line.cmd());
            if (cmd.size() >= 2 && cmd[0] == 'T' && std::all_of(cmd.begin() + 1, cmd.end(), [](char c) { return std::isdigit((unsigned char) c) != 0; })) {
                const int next = std::stoi(cmd.substr(1));
                if (next != tool && last_model_type[tool] == "Ironing") {
                    ++changes_after_ironing;
                    INFO("layer " << layer << ", tool " << tool << " to " << next);
                    const int expected = tool == 0 ? (layer <= 0 ? 225 : 220) : (layer <= 0 ? 235 : 230);
                    REQUIRE(target.count(tool) == 1);
                    CHECK(target.at(tool) == expected);
                }
                tool = next;
                return;
            }
            if (cmd == "M104" || cmd == "M109") {
                float s = 0.f, t = 0.f;
                if (line.has_value('S', s))
                    target[line.has_value('T', t) ? int(t) : tool] = int(s);
                return;
            }
            // Prime tower extrusions (ramming, wiping) are not model features: skip them, so the
            // tool still counts as having ironed last.
            if (line.extruding(self) && line.dist_XY(self) > EPSILON && type != "Prime tower")
                last_model_type[tool] = type;
        });
        REQUIRE(changes_after_ironing > 0);
    }
}
