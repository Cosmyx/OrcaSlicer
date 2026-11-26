// Checks of the CosmOS machine API readers of the "Machine information" tab
// (decision 0225). The samples are anonymised answers of a real machine: the
// serial numbers and versions are made up.

#include <catch2/catch_test_macros.hpp>
#include <catch2/matchers/catch_matchers_floating_point.hpp>

#include <optional>
#include <string>
#include <vector>

#include "slic3r/GUI/Cosmyx/logic/CosmyxPrinterConnectionInfo.hpp"

using namespace Slic3r::GUI::Cosmyx;

using Catch::Matchers::WithinAbs;

namespace {

void check_number(const std::optional<double>& value, double expected)
{
    REQUIRE(value.has_value());
    CHECK_THAT(*value, WithinAbs(expected, 1e-9));
}

const char* const k_device_sample = R"({"model":"Nova","serial":"1001-00000","software":"2.2.0-454-example","hardware":"1.2.1"})";

const char* const k_nozzles_sample = R"({"model":"nova","hardware_version":"1.2.1","heads":[{"head":0,"hotend":"standard","output":0.4,"hardened":false,"input":1.75,"direct":true,"max_temp":310.0,"hotends":["standard"]}],"outputs":null,"hotend_max_heads":{}})";

const char* const k_profile_sample = R"({
  "equipment_type": "3d_printer",
  "manufacturing_process": "fff",
  "make": "Cosmyx",
  "model": "Nova",
  "version": "1.2.1",
  "serial_number": "1001-00000",
  "equipment_properties": {
    "build_volume": {"shape": "box", "x": 300, "y": 300, "z": 300},
    "bed": {"heated": true, "maximum_temperature": 140},
    "layer_resolution": 0.1,
    "computer_controlled": true,
    "materials_worked": [{"material_type": "PLA"}],
    "uninterrupted_power_supply": false,
    "power_rating": 1000,
    "enclosure": {"extraction_system": true, "heated": false, "maximum_temperature": 60},
    "nozzles": [],
    "manager": {"firmware": {"type": "cosmos", "version": "2.2.0"}}
  },
  "parameters": {
    "led_count": 12,
    "bed_probe": {"type": "inductive", "contact": "nc", "link": "gpio"},
    "options": {"speed_mode": "speed", "high_temperature": true},
    "brand": "cosmyx"
  }
})";

} // namespace

TEST_CASE("The device identity is read", "[cosmyx][PrinterConnectionInfo]")
{
    const auto info = parse_device_info(k_device_sample);
    REQUIRE(info.has_value());
    CHECK(info->model == std::optional<std::string>("Nova"));
    CHECK(info->serial == std::optional<std::string>("1001-00000"));
    CHECK(info->software == std::optional<std::string>("2.2.0-454-example"));
    CHECK(info->hardware == std::optional<std::string>("1.2.1"));
}

TEST_CASE("Missing, null and wrongly typed identity fields stay unset", "[cosmyx][PrinterConnectionInfo]")
{
    const auto info = parse_device_info(R"({"model":null,"serial":12,"extra":"ignored","hardware":"1.0"})");
    REQUIRE(info.has_value());
    CHECK_FALSE(info->model.has_value());
    CHECK_FALSE(info->serial.has_value());
    CHECK_FALSE(info->software.has_value());
    CHECK(info->hardware == std::optional<std::string>("1.0"));
}

TEST_CASE("A body that is not a JSON object gives no result", "[cosmyx][PrinterConnectionInfo]")
{
    for (const char* body : {"", "not json", "[]", "null", "42", "\"text\"", "{\"model\":"}) {
        CHECK_FALSE(parse_device_info(body).has_value());
        CHECK_FALSE(parse_installed_options(body).has_value());
        CHECK_FALSE(parse_hot_ends(body).has_value());
        CHECK_FALSE(parse_camera(body).has_value());
    }
}

TEST_CASE("The installed options are read from the machine profile", "[cosmyx][PrinterConnectionInfo]")
{
    const auto options = parse_installed_options(k_profile_sample);
    REQUIRE(options.has_value());
    CHECK(options->speed_mode == std::optional<std::string>("speed"));
    CHECK(options->high_temperature == std::optional<bool>(true));
    CHECK(options->enclosure_heated == std::optional<bool>(false));
    CHECK(options->extraction_system == std::optional<bool>(true));
    check_number(options->enclosure_max_temperature, 60);
    CHECK(options->bed_heated == std::optional<bool>(true));
    check_number(options->bed_max_temperature, 140);
    CHECK(options->uninterrupted_power_supply == std::optional<bool>(false));
    check_number(options->build_volume_x, 300);
    check_number(options->build_volume_y, 300);
    check_number(options->build_volume_z, 300);
    CHECK(options->bed_probe == std::optional<std::string>("inductive"));
}

TEST_CASE("A partial machine profile leaves the missing options unset", "[cosmyx][PrinterConnectionInfo]")
{
    const auto options = parse_installed_options(
        R"({"equipment_properties":{"bed":null,"enclosure":"none","build_volume":{"x":250.5}},"parameters":{"options":{}}})");
    REQUIRE(options.has_value());
    CHECK_FALSE(options->speed_mode.has_value());
    CHECK_FALSE(options->high_temperature.has_value());
    CHECK_FALSE(options->bed_heated.has_value());
    CHECK_FALSE(options->enclosure_heated.has_value());
    check_number(options->build_volume_x, 250.5);
    CHECK_FALSE(options->build_volume_y.has_value());
    CHECK_FALSE(options->bed_probe.has_value());

    const auto empty = parse_installed_options("{}");
    REQUIRE(empty.has_value());
    CHECK_FALSE(empty->uninterrupted_power_supply.has_value());
}

TEST_CASE("The hot ends are read per head", "[cosmyx][PrinterConnectionInfo]")
{
    const auto hot_ends = parse_hot_ends(k_nozzles_sample);
    REQUIRE(hot_ends.has_value());
    REQUIRE(hot_ends->size() == 1);
    const HotEnd& first = hot_ends->front();
    CHECK(first.head == std::optional<long long>(0));
    CHECK(first.hotend == std::optional<std::string>("standard"));
    check_number(first.output, 0.4);
    CHECK(first.hardened == std::optional<bool>(false));
    check_number(first.max_temperature, 310);
    CHECK(first.direct == std::optional<bool>(true));
}

TEST_CASE("Junk head entries are skipped and null values stay unset", "[cosmyx][PrinterConnectionInfo]")
{
    const auto hot_ends = parse_hot_ends(
        R"({"heads":[{"head":0,"hotend":"standard","output":0.4},7,null,{"head":1,"hotend":"cht","output":null,"max_temp":null,"hardened":true}]})");
    REQUIRE(hot_ends.has_value());
    REQUIRE(hot_ends->size() == 2);
    CHECK((*hot_ends)[1].head == std::optional<long long>(1));
    CHECK((*hot_ends)[1].hotend == std::optional<std::string>("cht"));
    CHECK_FALSE((*hot_ends)[1].output.has_value());
    CHECK_FALSE((*hot_ends)[1].max_temperature.has_value());
    CHECK((*hot_ends)[1].hardened == std::optional<bool>(true));
    CHECK_FALSE((*hot_ends)[1].direct.has_value());
}

TEST_CASE("Missing or null heads give no hot end", "[cosmyx][PrinterConnectionInfo]")
{
    for (const char* body : {"{}", R"({"heads":null})", R"({"heads":{}})", R"({"heads":[]})"}) {
        const auto hot_ends = parse_hot_ends(body);
        REQUIRE(hot_ends.has_value());
        CHECK(hot_ends->empty());
    }
}

TEST_CASE("The camera status is read", "[cosmyx][PrinterConnectionInfo]")
{
    const auto online = parse_camera(R"({"online":true,"stream":{"format":"mjpeg","resolution":"1280x720","resolutions":[]}})");
    REQUIRE(online.has_value());
    CHECK(online->online == std::optional<bool>(true));
    const auto offline = parse_camera(R"({"online":false,"stream":null})");
    REQUIRE(offline.has_value());
    CHECK(offline->online == std::optional<bool>(false));
    const auto unknown = parse_camera("{}");
    REQUIRE(unknown.has_value());
    CHECK_FALSE(unknown->online.has_value());
}

TEST_CASE("Numbers are shown with at most two decimals", "[cosmyx][PrinterConnectionInfo]")
{
    CHECK(format_number(0.4) == "0.4");
    CHECK(format_number(310.0) == "310");
    CHECK(format_number(300) == "300");
    CHECK(format_number(1.756) == "1.76");
    CHECK(format_number(0.25) == "0.25");
    CHECK(format_number(0) == "0");
    CHECK(format_number(-0.001) == "0");
    CHECK(format_number(100.10) == "100.1");
}

TEST_CASE("The endpoint paths are the CosmOS ones", "[cosmyx][PrinterConnectionInfo]")
{
    CHECK(std::string(k_api_device) == "api/machine/device");
    CHECK(std::string(k_api_profile) == "api/machine/profile");
    CHECK(std::string(k_api_nozzles) == "api/machine/nozzles");
    CHECK(std::string(k_api_camera) == "api/camera");
}
