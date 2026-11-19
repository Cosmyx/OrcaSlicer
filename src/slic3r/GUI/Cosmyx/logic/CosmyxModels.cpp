#include "CosmyxModels.hpp"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include <Eigen/Geometry>
#include "nlohmann/json.hpp"

#include "libslic3r/Config.hpp"
#include "libslic3r/LocalesUtils.hpp"
#include "libslic3r/Model.hpp"
#include "libslic3r/libslic3r.h"

// Marks a string for xgettext; the menu translates it at display time. Kept
// in this file only: libslic3r/I18N.hpp refuses an L macro defined before it.
#ifndef L
#define L(s) s
#endif

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

using nlohmann::json;

// Keys of a region that describe the box rather than a print option.
bool is_box_key(const std::string& key)
{
    return key == "name" || key == "position" || key == "size" || key == "rotation";
}

std::string value_to_config_string(const std::string& key, const json& value)
{
    if (value.is_boolean())
        return value.get<bool>() ? "1" : "0";
    if (value.is_number_integer())
        return std::to_string(value.get<long long>());
    if (value.is_number())
        return float_to_string_decimal_point(value.get<double>());
    if (value.is_string())
        return value.get<std::string>();
    throw std::runtime_error("calibration preset: unsupported value for option '" + key + "'");
}

// Stores one JSON value into the config, checked against the print config
// definition (unknown keys and values of the wrong type are refused).
void set_option(DynamicPrintConfig& config, const std::string& key, const json& value)
{
    try {
        config.set_deserialize_strict(key, value_to_config_string(key, value));
    } catch (const std::exception& e) {
        throw std::runtime_error("calibration preset: invalid option '" + key + "': " + e.what());
    }
}

Vec3d read_vec3(const json& region, const char* key)
{
    const auto it = region.find(key);
    if (it == region.end() || !it->is_array() || it->size() != 3)
        throw std::runtime_error(std::string("calibration preset: region needs a 3-number array '") + key + "'");
    Vec3d out;
    for (size_t i = 0; i < 3; ++i) {
        if (!(*it)[i].is_number())
            throw std::runtime_error(std::string("calibration preset: '") + key + "' must hold numbers");
        out[i] = (*it)[i].get<double>();
    }
    return out;
}

} // namespace

const char* models_menu_label() { return L("Cosmyx 3D Models"); }

const char* group_label(ModelGroup group)
{
    switch (group) {
    case ModelGroup::DualHead: return L("Calibration Models Dual Head");
    case ModelGroup::SingleHead: return L("Calibration Models Single Head");
    case ModelGroup::Handy: return L("Cosmyx Handy Models");
    }
    return "";
}

const std::vector<ModelGroup>& model_groups()
{
    static const std::vector<ModelGroup> groups = { ModelGroup::DualHead, ModelGroup::SingleHead, ModelGroup::Handy };
    return groups;
}

const std::vector<CosmyxModel>& cosmyx_models()
{
    static const std::vector<CosmyxModel> models = {
        { "calage_1_sndt", ModelGroup::DualHead, L("Calage 1 SNDT"), "cosmyx/models/calibration/calage_1_sndt.3mf",
          ModelAction::SuggestZeroInfillDirection, "" },
        { "calage_2_sndt", ModelGroup::DualHead, L("Cosmyx Calage 2 SNDT"), "cosmyx/models/calibration/calage_2_sndt.3mf",
          ModelAction::Load, "" },
        { "calage_3_sndt", ModelGroup::DualHead, L("Cosmyx Calage 3 SNDT"), "cosmyx/models/calibration/calage_3_sndt.3mf",
          ModelAction::ApplyCalibrationPreset, "cosmyx/calibration/calage_3_modifiers.json" },
        { "cube_bicolore", ModelGroup::DualHead, L("Cube Bicolore"), "cosmyx/models/cube_bi_couleur.3mf",
          ModelAction::Load, "" },
        { "calage_1_nova", ModelGroup::SingleHead, L("Cosmyx Calage 1 Nova"), "cosmyx/models/calibration/calage_1_nova.3mf",
          ModelAction::SuggestZeroInfillDirection, "" },
        { "cosmyx_cube", ModelGroup::SingleHead, L("Cosmyx Cube"), "cosmyx/models/cosmyx_cube.3mf",
          ModelAction::Load, "" },
        { "control_tension_belt", ModelGroup::Handy, L("Control Tension Belt"), "cosmyx/models/control_tension_belt.stl",
          ModelAction::Load, "" },
        { "support_bobine", ModelGroup::Handy, L("Support Bobine"), "cosmyx/models/support_bobine_droit.3mf",
          ModelAction::Load, "" },
    };
    return models;
}

CalibrationPreset parse_calibration_preset(const std::string& json_text)
{
    json root;
    try {
        root = json::parse(json_text);
    } catch (const std::exception& e) {
        throw std::runtime_error(std::string("calibration preset: invalid JSON: ") + e.what());
    }
    if (!root.is_object())
        throw std::runtime_error("calibration preset: the root must be an object");

    CalibrationPreset preset;
    if (const auto base = root.find("base_settings"); base != root.end()) {
        if (!base->is_object())
            throw std::runtime_error("calibration preset: 'base_settings' must be an object");
        for (const auto& [key, value] : base->items())
            set_option(preset.base, key, value);
    }

    if (const auto regions = root.find("regions"); regions != root.end()) {
        if (!regions->is_array())
            throw std::runtime_error("calibration preset: 'regions' must be an array");
        for (const json& region : *regions) {
            if (!region.is_object())
                throw std::runtime_error("calibration preset: every region must be an object");
            ModifierBox box;
            if (const auto name = region.find("name"); name != region.end() && name->is_string())
                box.name = name->get<std::string>();
            box.position     = read_vec3(region, "position");
            box.size         = read_vec3(region, "size");
            box.rotation_deg = read_vec3(region, "rotation");
            for (size_t i = 0; i < 3; ++i)
                if (!std::isfinite(box.size[i]) || box.size[i] == 0.)
                    throw std::runtime_error("calibration preset: every size component must be non-zero");
            for (const auto& [key, value] : region.items())
                if (!is_box_key(key))
                    set_option(box.config, key, value);
            preset.boxes.push_back(std::move(box));
        }
    }
    return preset;
}

CalibrationPreset load_calibration_preset(const std::string& path)
{
    std::ifstream file(path, std::ios::binary);
    if (!file)
        throw std::runtime_error("calibration preset: cannot open " + path);
    std::ostringstream text;
    text << file.rdbuf();
    return parse_calibration_preset(text.str());
}

TriangleMesh make_modifier_mesh(const ModifierBox& box)
{
    // A cube with a negative size would be built inside out. Build it with the
    // absolute size and shift it so it spans the same space.
    const Vec3d size = box.size.cwiseAbs();
    const Vec3d shift(std::min(box.size.x(), 0.), std::min(box.size.y(), 0.), std::min(box.size.z(), 0.));

    // Same transform as the original menu: rotate about X, then Y, then Z, and
    // translate in the rotated frame (Eigen post-multiplies).
    Transform3d transform = Transform3d::Identity();
    transform.rotate(Eigen::AngleAxisd(box.rotation_deg.x() * PI / 180., Vec3d::UnitX()));
    transform.rotate(Eigen::AngleAxisd(box.rotation_deg.y() * PI / 180., Vec3d::UnitY()));
    transform.rotate(Eigen::AngleAxisd(box.rotation_deg.z() * PI / 180., Vec3d::UnitZ()));
    transform.translate(box.position + shift);

    TriangleMesh mesh = make_cube(size.x(), size.y(), size.z());
    mesh.transform(transform);
    return mesh;
}

bool needs_zero_infill_direction(const DynamicPrintConfig& config)
{
    for (const char* key : { "infill_direction", "solid_infill_direction" })
        if (const ConfigOption* opt = config.option(key); opt != nullptr && opt->getFloat() != 0.)
            return true;
    return false;
}

std::vector<std::string> differing_keys(const DynamicPrintConfig& wanted, const DynamicPrintConfig& current)
{
    std::vector<std::string> out;
    for (const std::string& key : wanted.keys()) {
        const ConfigOption* have = current.option(key);
        if (have == nullptr || *have != *wanted.option(key))
            out.push_back(key);
    }
    return out;
}

size_t apply_calibration_modifiers(ModelObject& object, const CalibrationPreset& preset)
{
    // Modifiers baked into the shipped file are replaced by the preset's boxes.
    // ModelObject::delete_volume() is not used: when one volume is left it
    // folds that volume's transform into the instances, which would move the
    // frame the boxes are placed in.
    auto& volumes = object.volumes;
    for (auto it = volumes.begin(); it != volumes.end();) {
        if ((*it)->type() == ModelVolumeType::PARAMETER_MODIFIER) {
            delete *it;
            it = volumes.erase(it);
        } else
            ++it;
    }

    for (const ModifierBox& box : preset.boxes) {
        ModelVolume* volume = object.add_volume(make_modifier_mesh(box), ModelVolumeType::PARAMETER_MODIFIER,
                                                false /* the box is already placed */);
        volume->name = box.name;
        volume->config.apply(box.config);
        // A modifier without an extruder setting is not initialised properly
        // by the object list; 0 means "inherit from the object".
        if (!volume->config.has("extruder"))
            volume->config.set_key_value("extruder", new ConfigOptionInt(0));
        volume->source.is_from_builtin_objects = true;
    }
    object.invalidate_bounding_box();
    return preset.boxes.size();
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
