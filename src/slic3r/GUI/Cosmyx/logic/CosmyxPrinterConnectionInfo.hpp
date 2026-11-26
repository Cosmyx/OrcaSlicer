#ifndef slic3r_GUI_Cosmyx_CosmyxPrinterConnectionInfo_hpp_
#define slic3r_GUI_Cosmyx_CosmyxPrinterConnectionInfo_hpp_

// wxWidgets-free readers of the CosmOS machine API answers shown in the
// "Machine information" tab of the Cosmyx physical printer dialog (decision
// 0225). Each reader takes the JSON body of one endpoint and returns what the
// tab shows. They are tolerant: a missing, null or wrongly typed field leaves
// its value unset, and unknown fields are ignored. Only a body that is not a
// JSON object gives no result at all.
//
// Standard library and nlohmann::json only; compiled into libslic3r_gui and
// into cosmyx_tests.

#include <optional>
#include <string>
#include <vector>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

// Endpoint paths, relative to the machine root (see cosmos_api_url()).
extern const char* const k_api_device;  // "api/machine/device"
extern const char* const k_api_profile; // "api/machine/profile"
extern const char* const k_api_nozzles; // "api/machine/nozzles"
extern const char* const k_api_camera;  // "api/camera"

// GET /api/machine/device
struct DeviceInfo
{
    std::optional<std::string> model;
    std::optional<std::string> serial;
    std::optional<std::string> software;
    std::optional<std::string> hardware;
};

// GET /api/machine/profile, the installed options.
struct InstalledOptions
{
    // parameters.options
    std::optional<std::string> speed_mode;
    std::optional<bool>        high_temperature;
    // equipment_properties.enclosure
    std::optional<bool>   enclosure_heated;
    std::optional<bool>   extraction_system;
    std::optional<double> enclosure_max_temperature;
    // equipment_properties.bed
    std::optional<bool>   bed_heated;
    std::optional<double> bed_max_temperature;
    // equipment_properties.uninterrupted_power_supply
    std::optional<bool> uninterrupted_power_supply;
    // equipment_properties.build_volume
    std::optional<double> build_volume_x;
    std::optional<double> build_volume_y;
    std::optional<double> build_volume_z;
    // parameters.bed_probe.type
    std::optional<std::string> bed_probe;
};

// One entry of heads[] of GET /api/machine/nozzles.
struct HotEnd
{
    std::optional<long long>   head;
    std::optional<std::string> hotend;
    // Nozzle diameter, mm.
    std::optional<double> output;
    std::optional<bool>   hardened;
    std::optional<double> max_temperature;
    std::optional<bool>   direct;
};

// GET /api/camera
struct CameraInfo
{
    std::optional<bool> online;
};

std::optional<DeviceInfo>          parse_device_info(const std::string& body);
std::optional<InstalledOptions>    parse_installed_options(const std::string& body);
// A missing or null heads[] gives an empty list; entries that are not objects are skipped.
std::optional<std::vector<HotEnd>> parse_hot_ends(const std::string& body);
std::optional<CameraInfo>          parse_camera(const std::string& body);

// A number as the tab shows it: up to two decimals, trailing zeros removed,
// '.' as the decimal separator (0.4 -> "0.4", 310.0 -> "310", 1.756 -> "1.76").
std::string format_number(double value);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_CosmyxPrinterConnectionInfo_hpp_
