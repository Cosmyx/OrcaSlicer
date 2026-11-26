// Checks of the CHT nozzle type: its position in the nozzle_type choices, the
// enum and string maps, its serialization and its hardness.

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <cstddef>
#include <iterator>
#include <string>
#include <vector>

#include <boost/filesystem/path.hpp>
#include <boost/nowide/fstream.hpp>

#include "nlohmann/json.hpp"

#include "libslic3r/CommonDefs.hpp"
#include "libslic3r/Config.hpp"
#include "libslic3r/Print.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "libslic3r/Utils.hpp"
#include "libslic3r/Cosmyx/ConfigDefExtensions.hpp"

using namespace Slic3r;

namespace {

// Folder that holds info/nozzle_info.json: the parent of resources/profiles.
std::string resources_folder()
{
    return boost::filesystem::path(std::string(PROFILES_DIR)).parent_path().string();
}

std::ptrdiff_t index_of(const std::vector<std::string>& values, const std::string& value)
{
    const auto it = std::find(values.begin(), values.end(), value);
    return it == values.end() ? -1 : std::distance(values.begin(), it);
}

} // namespace

TEST_CASE("CHT sits at the position of its enum value in nozzle_type", "[cosmyx][ChtNozzle]")
{
    // The GUI stores the combo box position as the enum value, so the two must match.
    const ConfigOptionDef* opt = print_config_def.get("nozzle_type");
    REQUIRE(opt != nullptr);
    REQUIRE(opt->enum_values.size() == opt->enum_labels.size());

    const std::ptrdiff_t index = index_of(opt->enum_values, "cht");
    CHECK(index == std::ptrdiff_t(int(ntCHT)));
    REQUIRE(index >= 0);
    CHECK(opt->enum_labels[std::size_t(index)] == "CHT");

    // Every choice keeps the enum value of its position.
    for (std::size_t i = 0; i < opt->enum_values.size(); ++i) {
        INFO("choice " << opt->enum_values[i]);
        CHECK(opt->enum_keys_map->at(opt->enum_values[i]) == int(i));
    }
}

TEST_CASE("CHT keeps the upstream nozzle types", "[cosmyx][ChtNozzle]")
{
    const ConfigOptionDef* opt = print_config_def.get("nozzle_type");
    REQUIRE(opt != nullptr);
    for (const char* key : {"undefine", "hardened_steel", "stainless_steel", "tungsten_carbide", "brass"})
        CHECK(index_of(opt->enum_values, key) >= 0);
    CHECK(index_of(opt->enum_values, "tungsten_carbide") == std::ptrdiff_t(int(ntTungstenCarbide)));
    CHECK(index_of(opt->enum_labels, "Tungsten carbide") == std::ptrdiff_t(int(ntTungstenCarbide)));
}

TEST_CASE("CHT extender is idempotent", "[cosmyx][ChtNozzle]")
{
    PrintConfigDef def;
    const std::vector<std::string> values = def.get("nozzle_type")->enum_values;
    const std::vector<std::string> labels = def.get("nozzle_type")->enum_labels;
    Cosmyx::extend_cht_nozzle(def);
    CHECK(def.get("nozzle_type")->enum_values == values);
    CHECK(def.get("nozzle_type")->enum_labels == labels);
}

TEST_CASE("CHT enum and string maps round-trip", "[cosmyx][ChtNozzle]")
{
    CHECK(NozzleTypeEumnToStr.at(ntCHT) == "cht");
    CHECK(NozzleTypeStrToEumn.at("cht") == ntCHT);
    for (const auto& [type, name] : NozzleTypeEumnToStr) {
        INFO("nozzle type " << name);
        CHECK(NozzleTypeStrToEumn.at(name) == type);
    }

    const t_config_enum_values& keys = ConfigOptionEnum<NozzleType>::get_enum_values();
    CHECK(keys.at("cht") == int(ntCHT));
    CHECK(ConfigOptionEnum<NozzleType>::get_enum_names().at(std::size_t(int(ntCHT))) == "cht");
}

TEST_CASE("A config with nozzle_type cht loads and saves", "[cosmyx][ChtNozzle]")
{
    DynamicPrintConfig config;
    config.set_deserialize_strict("nozzle_type", "cht");
    const auto* opt = config.option<ConfigOptionEnumsGenericNullable>("nozzle_type");
    REQUIRE(opt != nullptr);
    REQUIRE(opt->values.size() == 1);
    CHECK(opt->values.front() == int(ntCHT));
    CHECK(opt->serialize() == "cht");

    config.set_deserialize_strict("nozzle_type", "cht,tungsten_carbide");
    opt = config.option<ConfigOptionEnumsGenericNullable>("nozzle_type");
    CHECK(opt->values == std::vector<int>{int(ntCHT), int(ntTungstenCarbide)});
    CHECK(opt->serialize() == "cht,tungsten_carbide");
}

TEST_CASE("nozzle_info.json gives CHT and tungsten carbide their hardness", "[cosmyx][ChtNozzle]")
{
    const boost::filesystem::path file = boost::filesystem::path(resources_folder()) / "info" / "nozzle_info.json";
    boost::nowide::ifstream in(file.string());
    REQUIRE(in.good());
    const nlohmann::json j = nlohmann::json::parse(in);
    CHECK(j["nozzle_hrc"]["cht"].get<int>() == 65);
    CHECK(j["nozzle_hrc"]["tungsten_carbide"].get<int>() == 85);
}

TEST_CASE("Print reports the CHT hardness", "[cosmyx][ChtNozzle]")
{
    // get_hrc_by_nozzle_type() reads nozzle_info.json from resources_dir() once
    // and caches it; the real resources folder is set before the first call.
    const std::string previous = resources_dir();
    set_resources_dir(resources_folder());
    CHECK(Print::get_hrc_by_nozzle_type(ntCHT) == 65);
    CHECK(Print::get_hrc_by_nozzle_type(ntTungstenCarbide) == 85);
    CHECK(Print::get_hrc_by_nozzle_type(ntHardenedSteel) == 55);
    set_resources_dir(previous);
}
