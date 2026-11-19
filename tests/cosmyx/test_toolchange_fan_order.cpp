// Order of the tool change and of the new tool's fan command in the cooling
// pass. On printers with one part cooling fan per tool (Klipper toolchangers,
// IDEX), M106 drives the fan of the active tool: the fan command for the new
// tool must come after its Tn, or it lands on the tool being parked and the new
// tool prints with the previous tool's fan state.

#include <catch2/catch_test_macros.hpp>

#include <cstdlib>
#include <optional>
#include <sstream>
#include <string>
#include <vector>

#include "libslic3r/Config.hpp"
#include "libslic3r/PrintConfig.hpp"

#include "test_helpers.hpp"

using namespace Slic3r;
using namespace Slic3r::Test;

namespace {

// 30% and 80% as the cooling pass writes them: M106 S<255.5 * percent / 100>.
constexpr int fan_30_percent = 76;
constexpr int fan_80_percent = 204;

// The same value for each of `filaments` filaments, as a vector option reads it.
std::string per_filament(const std::string &value, unsigned int filaments)
{
    std::string out;
    for (unsigned int i = 0; i < filaments; ++i)
        out += (i ? "," : "") + value;
    return out;
}

// Gives filament i the constant part cooling fan speed speeds[i] (percent) on
// every layer, the first one included, whatever the layer time: the minimum
// and maximum speeds are equal, the fan never stops for a long layer, and no
// first-layer gate, ramp, overhang fan or slowdown changes it.
void set_constant_fan(DynamicPrintConfig &config, const std::vector<std::string> &speeds)
{
    const unsigned int filaments = unsigned(speeds.size());
    std::string        joined;
    for (size_t i = 0; i < speeds.size(); ++i)
        joined += (i ? "," : "") + speeds[i];
    config.set_deserialize_strict("fan_min_speed", joined);
    config.set_deserialize_strict("fan_max_speed", joined);
    config.set_deserialize_strict("reduce_fan_stop_start_freq", per_filament("1", filaments));
    config.set_deserialize_strict("close_fan_the_first_x_layers", per_filament("0", filaments));
    config.set_deserialize_strict("full_fan_speed_layer", per_filament("0", filaments));
    config.set_deserialize_strict("enable_overhang_bridge_fan", per_filament("0", filaments));
    config.set_deserialize_strict("slow_down_for_layer_cooling", per_filament("0", filaments));
    config.set_deserialize_strict({
        { "use_relative_e_distances",   true },
        { "enable_prime_tower",         false },
        { "enable_support",             false },
        { "skirt_loops",                0 },
        { "brim_type",                  "no_brim" },
        { "layer_height",               0.2 },
        { "initial_layer_print_height", 0.2 },
    });
}

DynamicPrintConfig two_filament_config()
{
    DynamicPrintConfig config = multifilament_config(2);
    set_constant_fan(config, { "30", "80" });
    return config;
}

DynamicPrintConfig one_filament_config()
{
    DynamicPrintConfig config = DynamicPrintConfig::full_print_config();
    set_constant_fan(config, { "30" });
    return config;
}

std::vector<std::string> split_lines(const std::string &gcode)
{
    std::vector<std::string> lines;
    std::istringstream       input(gcode);
    std::string              line;
    while (std::getline(input, line))
        lines.push_back(line);
    return lines;
}

bool starts_with(const std::string &line, const char *prefix)
{
    return line.rfind(prefix, 0) == 0;
}

// The part cooling fan speed a line sets (M106 S<n>, M107), if it sets one.
std::optional<int> fan_command(const std::string &line)
{
    if (starts_with(line, "M107"))
        return 0;
    if (starts_with(line, "M106 S"))
        return std::atoi(line.c_str() + 6);
    return std::nullopt;
}

// The tool a bare tool change line selects (T<n>), if it is one.
std::optional<int> tool_change(const std::string &line)
{
    if (line.size() < 2 || line[0] != 'T' || line[1] < '0' || line[1] > '9')
        return std::nullopt;
    return std::atoi(line.c_str() + 1);
}

// A move in the XY plane that pushes filament (relative E, so E > 0). Leaves
// out retractions, unretractions and wipes.
bool is_extrusion(const std::string &line)
{
    if (!(starts_with(line, "G1 ") || starts_with(line, "G2 ") || starts_with(line, "G3 ")))
        return false;
    const std::string move = line.substr(0, line.find(';'));
    const size_t      e    = move.find(" E");
    if (e == std::string::npos || (move.find(" X") == std::string::npos && move.find(" Y") == std::string::npos))
        return false;
    return std::atof(move.c_str() + e + 2) > 0.;
}

// One tool change made between two extrusions, with the fan commands found
// on each side of it.
struct ToolChange
{
    int              tool;
    std::vector<int> fan_before; // between the previous extrusion and the Tn
    std::vector<int> fan_after;  // between the Tn and the next extrusion
};

// The tool changes made after the first extrusion and followed by another one.
std::vector<ToolChange> mid_print_tool_changes(const std::string &gcode)
{
    std::vector<ToolChange> changes;
    std::vector<int>        fan_since_extrusion;
    std::optional<size_t>   open_change;
    bool                    extruded = false;
    for (const std::string &line : split_lines(gcode)) {
        if (is_extrusion(line)) {
            extruded = true;
            open_change.reset();
            fan_since_extrusion.clear();
        } else if (const std::optional<int> tool = tool_change(line); tool && extruded) {
            changes.push_back({ *tool, fan_since_extrusion, {} });
            open_change = changes.size() - 1;
        } else if (const std::optional<int> fan = fan_command(line)) {
            if (open_change)
                changes[*open_change].fan_after.push_back(*fan);
            else
                fan_since_extrusion.push_back(*fan);
        }
    }
    // A tool change with no extrusion after it belongs to the end G-code.
    if (open_change)
        changes.pop_back();
    return changes;
}

std::string two_cubes_on_two_filaments(const DynamicPrintConfig &config)
{
    return slice_with_object_overrides({ cube(10), cube(10) }, config, { { { "extruder", "1" } }, { { "extruder", "2" } } });
}

} // namespace

TEST_CASE("The new tool's fan command follows its tool change", "[cosmyx][Cooling]")
{
    const std::vector<ToolChange> changes = mid_print_tool_changes(two_cubes_on_two_filaments(two_filament_config()));
    REQUIRE(changes.size() >= 2);
    for (const ToolChange &change : changes) {
        CAPTURE(change.tool, change.fan_before, change.fan_after);
        REQUIRE(change.tool >= 0);
        REQUIRE(change.tool <= 1);
        // Nothing drives the fan of the tool being parked.
        CHECK(change.fan_before.empty());
        // The new tool gets its own speed once it is active.
        REQUIRE_FALSE(change.fan_after.empty());
        CHECK(change.fan_after.back() == (change.tool == 0 ? fan_30_percent : fan_80_percent));
    }
}

TEST_CASE("A single filament print keeps one fan speed and no tool change", "[cosmyx][Cooling]")
{
    const std::string gcode = slice({ cube(10) }, one_filament_config());
    CHECK(mid_print_tool_changes(gcode).empty());
    bool fan_on = false;
    for (const std::string &line : split_lines(gcode))
        if (const std::optional<int> fan = fan_command(line); fan && *fan != 0) {
            CHECK(*fan == fan_30_percent);
            fan_on = true;
        }
    CHECK(fan_on);
}

TEST_CASE("A tool change inside the belt band leaves the fan off", "[cosmyx][Cooling]")
{
    // The band tags GCode::_extrude() writes on belt printers, injected at each
    // layer change so every layer of this flat print lies inside the band.
    DynamicPrintConfig config = two_filament_config();
    config.set_deserialize_strict({ { "layer_change_gcode", ";_BELT_BAND_START" } });
    const std::vector<ToolChange> changes = mid_print_tool_changes(two_cubes_on_two_filaments(config));
    REQUIRE(changes.size() >= 2);
    for (const ToolChange &change : changes) {
        CAPTURE(change.tool, change.fan_before, change.fan_after);
        CHECK(change.fan_before.empty());
        REQUIRE_FALSE(change.fan_after.empty());
        CHECK(change.fan_after.back() == 0);
    }
}
