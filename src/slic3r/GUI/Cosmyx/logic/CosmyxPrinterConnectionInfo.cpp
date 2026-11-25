#include "CosmyxPrinterConnectionInfo.hpp"

#include <cmath>
#include <cstddef>
#include <cstdio>
#include <initializer_list>
#include <string>

#include <nlohmann/json.hpp>

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

const char* const k_api_device  = "api/machine/device";
const char* const k_api_profile = "api/machine/profile";
const char* const k_api_nozzles = "api/machine/nozzles";
const char* const k_api_camera  = "api/camera";

namespace {

using json = nlohmann::json;

std::optional<json> parse_object(const std::string& body)
{
    // No exceptions: a body that is not JSON is "discarded", never thrown.
    json value = json::parse(body, nullptr, false);
    if (value.is_discarded() || !value.is_object())
        return std::nullopt;
    return value;
}

// The member at path, or null when any step is missing or not an object.
const json* member(const json& object, std::initializer_list<const char*> path)
{
    const json* node = &object;
    for (const char* key : path) {
        if (!node->is_object())
            return nullptr;
        const auto it = node->find(key);
        if (it == node->end())
            return nullptr;
        node = &*it;
    }
    return node;
}

std::optional<std::string> string_at(const json& object, std::initializer_list<const char*> path)
{
    const json* node = member(object, path);
    if (node == nullptr || !node->is_string())
        return std::nullopt;
    return node->get<std::string>();
}

std::optional<bool> bool_at(const json& object, std::initializer_list<const char*> path)
{
    const json* node = member(object, path);
    if (node == nullptr || !node->is_boolean())
        return std::nullopt;
    return node->get<bool>();
}

std::optional<double> number_at(const json& object, std::initializer_list<const char*> path)
{
    const json* node = member(object, path);
    if (node == nullptr || !node->is_number())
        return std::nullopt;
    return node->get<double>();
}

std::optional<long long> integer_at(const json& object, std::initializer_list<const char*> path)
{
    const json* node = member(object, path);
    if (node == nullptr || !node->is_number_integer())
        return std::nullopt;
    return node->get<long long>();
}

} // namespace

std::optional<DeviceInfo> parse_device_info(const std::string& body)
{
    const std::optional<json> root = parse_object(body);
    if (!root)
        return std::nullopt;
    DeviceInfo info;
    info.model    = string_at(*root, {"model"});
    info.serial   = string_at(*root, {"serial"});
    info.software = string_at(*root, {"software"});
    info.hardware = string_at(*root, {"hardware"});
    return info;
}

std::optional<InstalledOptions> parse_installed_options(const std::string& body)
{
    const std::optional<json> root = parse_object(body);
    if (!root)
        return std::nullopt;
    InstalledOptions options;
    options.speed_mode                 = string_at(*root, {"parameters", "options", "speed_mode"});
    options.high_temperature           = bool_at(*root, {"parameters", "options", "high_temperature"});
    options.enclosure_heated           = bool_at(*root, {"equipment_properties", "enclosure", "heated"});
    options.extraction_system          = bool_at(*root, {"equipment_properties", "enclosure", "extraction_system"});
    options.enclosure_max_temperature  = number_at(*root, {"equipment_properties", "enclosure", "maximum_temperature"});
    options.bed_heated                 = bool_at(*root, {"equipment_properties", "bed", "heated"});
    options.bed_max_temperature        = number_at(*root, {"equipment_properties", "bed", "maximum_temperature"});
    options.uninterrupted_power_supply = bool_at(*root, {"equipment_properties", "uninterrupted_power_supply"});
    options.build_volume_x             = number_at(*root, {"equipment_properties", "build_volume", "x"});
    options.build_volume_y             = number_at(*root, {"equipment_properties", "build_volume", "y"});
    options.build_volume_z             = number_at(*root, {"equipment_properties", "build_volume", "z"});
    options.bed_probe                  = string_at(*root, {"parameters", "bed_probe", "type"});
    return options;
}

std::optional<std::vector<HotEnd>> parse_hot_ends(const std::string& body)
{
    const std::optional<json> root = parse_object(body);
    if (!root)
        return std::nullopt;
    std::vector<HotEnd> hot_ends;
    const json*         heads = member(*root, {"heads"});
    if (heads == nullptr || !heads->is_array())
        return hot_ends;
    for (const json& entry : *heads) {
        if (!entry.is_object())
            continue;
        HotEnd hot_end;
        hot_end.head            = integer_at(entry, {"head"});
        hot_end.hotend          = string_at(entry, {"hotend"});
        hot_end.output          = number_at(entry, {"output"});
        hot_end.hardened        = bool_at(entry, {"hardened"});
        hot_end.max_temperature = number_at(entry, {"max_temp"});
        hot_end.direct          = bool_at(entry, {"direct"});
        hot_ends.push_back(hot_end);
    }
    return hot_ends;
}

std::optional<CameraInfo> parse_camera(const std::string& body)
{
    const std::optional<json> root = parse_object(body);
    if (!root)
        return std::nullopt;
    CameraInfo camera;
    camera.online = bool_at(*root, {"online"});
    return camera;
}

std::string format_number(double value)
{
    if (!std::isfinite(value))
        return {};
    char buffer[64];
    // snprintf follows LC_NUMERIC, which may give ',' as the separator.
    std::snprintf(buffer, sizeof(buffer), "%.2f", std::round(value * 100.0) / 100.0);
    std::string text = buffer;
    const std::size_t dot = text.find_first_of(".,");
    if (dot != std::string::npos) {
        while (!text.empty() && text.back() == '0')
            text.pop_back();
        if (!text.empty() && (text.back() == '.' || text.back() == ','))
            text.pop_back();
        if (dot < text.size())
            text[dot] = '.';
    }
    if (text == "-0")
        text = "0";
    return text;
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
