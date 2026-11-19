// Checks of the Cosmyx 3D models catalogue: every shipped file exists and
// loads, the calibration preset parses, and its modifier boxes land where the
// original Cosmyx menu put them.

#include <catch2/catch_test_macros.hpp>
#include <catch2/matchers/catch_matchers_floating_point.hpp>

#include <algorithm>
#include <cctype>
#include <set>
#include <string>
#include <vector>

#include <boost/filesystem/operations.hpp>
#include <boost/filesystem/path.hpp>

#include "libslic3r/BoundingBox.hpp"
#include "libslic3r/Model.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "libslic3r/TriangleMesh.hpp"
#include "slic3r/GUI/Cosmyx/logic/CosmyxModels.hpp"

using namespace Slic3r;
using namespace Slic3r::GUI::Cosmyx;
using Catch::Matchers::WithinAbs;
using Catch::Matchers::WithinRel;
namespace fs = boost::filesystem;

namespace {

// PROFILES_DIR is <source>/resources/profiles.
fs::path resources_root() { return fs::path(PROFILES_DIR).parent_path(); }

fs::path shipped(const std::string& rel_path) { return resources_root() / fs::path(rel_path); }

bool is_portable_rel_path(const std::string& rel_path)
{
    return !rel_path.empty() && rel_path.front() != '/' && std::all_of(rel_path.begin(), rel_path.end(), [](char c) {
        return std::islower(static_cast<unsigned char>(c)) || std::isdigit(static_cast<unsigned char>(c)) ||
               c == '_' || c == '.' || c == '/';
    });
}

const char* const k_preset_rel_path = "cosmyx/calibration/calage_3_modifiers.json";

} // namespace

TEST_CASE("Every Cosmyx model is shipped under a portable path", "[cosmyx]")
{
    REQUIRE_FALSE(cosmyx_models().empty());
    std::set<std::string> keys;
    for (const CosmyxModel& model : cosmyx_models()) {
        INFO("model " << model.key);
        CHECK(keys.insert(model.key).second);
        CHECK(std::string(model.label).size() > 0);
        CHECK(is_portable_rel_path(model.rel_path));
        CHECK(fs::is_regular_file(shipped(model.rel_path)));
        if (model.action == ModelAction::ApplyCalibrationPreset) {
            CHECK(is_portable_rel_path(model.preset_rel_path));
            CHECK(fs::is_regular_file(shipped(model.preset_rel_path)));
        } else {
            CHECK(model.preset_rel_path.empty());
        }
    }
}

TEST_CASE("Every Cosmyx group has models and a label", "[cosmyx]")
{
    CHECK(std::string(models_menu_label()) == "Cosmyx 3D Models");
    for (ModelGroup group : model_groups()) {
        CHECK(std::string(group_label(group)).size() > 0);
        CHECK(std::any_of(cosmyx_models().begin(), cosmyx_models().end(),
                          [group](const CosmyxModel& m) { return m.group == group; }));
    }
}

TEST_CASE("Every Cosmyx model file loads", "[cosmyx]")
{
    for (const CosmyxModel& model : cosmyx_models()) {
        INFO("model " << model.key);
        Model loaded;
        REQUIRE_NOTHROW(loaded = Model::read_from_file(shipped(model.rel_path).string(), nullptr, nullptr,
                                                       LoadStrategy::LoadModel | LoadStrategy::AddDefaultInstances));
        CHECK_FALSE(loaded.objects.empty());
    }
}

TEST_CASE("The shipped Calage 3 preset parses", "[cosmyx]")
{
    const CalibrationPreset preset = load_calibration_preset(shipped(k_preset_rel_path).string());

    CHECK_THAT(preset.base.opt_float("infill_direction"), WithinAbs(90., 1e-9));
    CHECK_THAT(preset.base.opt_float("solid_infill_direction"), WithinAbs(90., 1e-9));
    CHECK(preset.base.opt_bool("only_one_wall_first_layer"));

    REQUIRE(preset.boxes.size() == 1);
    const ModifierBox& box = preset.boxes.front();
    CHECK(box.name == "Infill 0° Region");
    CHECK(box.position.isApprox(Vec3d(-25., 0., -60.)));
    CHECK(box.size.isApprox(Vec3d(150., -5., 60.)));
    CHECK(box.rotation_deg.isApprox(Vec3d(0., 90., 0.)));
    CHECK_THAT(box.config.opt_float("infill_direction"), WithinAbs(0., 1e-9));
    CHECK_THAT(box.config.opt_float("solid_infill_direction"), WithinAbs(0., 1e-9));
    CHECK(box.config.opt_bool("only_one_wall_first_layer"));
}

TEST_CASE("A malformed calibration preset is refused", "[cosmyx]")
{
    CHECK_THROWS_AS(parse_calibration_preset("not json"), std::runtime_error);
    CHECK_THROWS_AS(parse_calibration_preset("[]"), std::runtime_error);
    CHECK_THROWS_AS(parse_calibration_preset(R"({"base_settings": {"no_such_option": 1}})"), std::runtime_error);
    CHECK_THROWS_AS(parse_calibration_preset(R"({"regions": [{"position": [0, 0], "size": [1, 1, 1], "rotation": [0, 0, 0]}]})"),
                    std::runtime_error);
    CHECK_THROWS_AS(parse_calibration_preset(R"({"regions": [{"position": [0, 0, 0], "size": [1, 0, 1], "rotation": [0, 0, 0]}]})"),
                    std::runtime_error);
    CHECK_THROWS_AS(load_calibration_preset((resources_root() / "cosmyx" / "no_such_file.json").string()), std::runtime_error);

    const CalibrationPreset empty = parse_calibration_preset("{}");
    CHECK(empty.base.empty());
    CHECK(empty.boxes.empty());
}

TEST_CASE("A modifier box mesh keeps the original placement and faces outwards", "[cosmyx]")
{
    const CalibrationPreset preset = load_calibration_preset(shipped(k_preset_rel_path).string());
    REQUIRE(preset.boxes.size() == 1);
    const TriangleMesh mesh = make_modifier_mesh(preset.boxes.front());

    // Rotation of 90 degrees about Y, translation in the rotated frame:
    // (x, y, z) -> (z - 60, y, 25 - x) for x in [0, 150], y in [-5, 0], z in [0, 60].
    const BoundingBoxf3 bb = mesh.bounding_box();
    CHECK_THAT(bb.min.x(), WithinAbs(-60., 1e-4));
    CHECK_THAT(bb.max.x(), WithinAbs(0., 1e-4));
    CHECK_THAT(bb.min.y(), WithinAbs(-5., 1e-4));
    CHECK_THAT(bb.max.y(), WithinAbs(0., 1e-4));
    CHECK_THAT(bb.min.z(), WithinAbs(-125., 1e-4));
    CHECK_THAT(bb.max.z(), WithinAbs(25., 1e-4));
    CHECK_THAT(its_volume(mesh.its), WithinRel(150. * 5. * 60., 1e-5));
}

TEST_CASE("The zero infill direction suggestion triggers on any non-zero direction", "[cosmyx]")
{
    DynamicPrintConfig config;
    config.set_key_value("infill_direction", new ConfigOptionFloat(0.));
    config.set_key_value("solid_infill_direction", new ConfigOptionFloat(0.));
    CHECK_FALSE(needs_zero_infill_direction(config));
    config.set_key_value("solid_infill_direction", new ConfigOptionFloat(45.));
    CHECK(needs_zero_infill_direction(config));
    config.set_key_value("solid_infill_direction", new ConfigOptionFloat(0.));
    config.set_key_value("infill_direction", new ConfigOptionFloat(90.));
    CHECK(needs_zero_infill_direction(config));
    CHECK_FALSE(needs_zero_infill_direction(DynamicPrintConfig()));
}

TEST_CASE("Only the preset settings that differ are reported", "[cosmyx]")
{
    const CalibrationPreset preset = load_calibration_preset(shipped(k_preset_rel_path).string());
    DynamicPrintConfig current;
    current.set_key_value("infill_direction", new ConfigOptionFloat(90.));
    current.set_key_value("solid_infill_direction", new ConfigOptionFloat(45.));

    std::vector<std::string> keys = differing_keys(preset.base, current);
    std::sort(keys.begin(), keys.end());
    CHECK(keys == std::vector<std::string>{ "only_one_wall_first_layer", "solid_infill_direction" });

    current.apply_only(preset.base, keys);
    CHECK(differing_keys(preset.base, current).empty());
}

TEST_CASE("Calibration modifiers replace only the modifiers of the given object", "[cosmyx]")
{
    const CalibrationPreset preset = load_calibration_preset(shipped(k_preset_rel_path).string());

    Model model;
    ModelObject* target = model.add_object();
    target->add_volume(make_cube(20., 20., 20.));
    ModelVolume* old_modifier = target->add_volume(make_cube(5., 5., 5.), ModelVolumeType::PARAMETER_MODIFIER);
    old_modifier->name = "baked";
    target->add_instance();

    ModelObject* other = model.add_object();
    other->add_volume(make_cube(10., 10., 10.));
    other->add_volume(make_cube(2., 2., 2.), ModelVolumeType::PARAMETER_MODIFIER);
    other->add_instance();

    CHECK(apply_calibration_modifiers(*target, preset) == 1);

    REQUIRE(target->volumes.size() == 2);
    CHECK(target->volumes[0]->type() == ModelVolumeType::MODEL_PART);
    const ModelVolume& added = *target->volumes[1];
    CHECK(added.type() == ModelVolumeType::PARAMETER_MODIFIER);
    CHECK(added.name == "Infill 0° Region");
    CHECK_THAT(added.config.opt_float("infill_direction"), WithinAbs(0., 1e-9));
    CHECK_THAT(added.config.opt_float("solid_infill_direction"), WithinAbs(0., 1e-9));
    CHECK(added.config.get().opt_bool("only_one_wall_first_layer"));
    CHECK(added.config.extruder() == 0);
    CHECK(added.source.is_from_builtin_objects);
    CHECK_THAT(added.mesh().bounding_box().min.z(), WithinAbs(-125., 1e-4));

    // The other object keeps its own modifier.
    REQUIRE(other->volumes.size() == 2);
    CHECK(other->volumes[1]->type() == ModelVolumeType::PARAMETER_MODIFIER);
}

TEST_CASE("Calibration modifiers apply to the shipped Calage 3 model", "[cosmyx]")
{
    const CalibrationPreset preset = load_calibration_preset(shipped(k_preset_rel_path).string());
    Model model = Model::read_from_file(shipped("cosmyx/models/calibration/calage_3_sndt.3mf").string(), nullptr, nullptr,
                                        LoadStrategy::LoadModel | LoadStrategy::AddDefaultInstances);
    REQUIRE_FALSE(model.objects.empty());
    ModelObject& object = *model.objects.front();
    const auto parts = std::count_if(object.volumes.begin(), object.volumes.end(),
                                       [](const ModelVolume* v) { return v->type() == ModelVolumeType::MODEL_PART; });

    apply_calibration_modifiers(object, preset);

    const auto modifiers = std::count_if(object.volumes.begin(), object.volumes.end(),
                                           [](const ModelVolume* v) { return v->type() == ModelVolumeType::PARAMETER_MODIFIER; });
    CHECK(size_t(modifiers) == preset.boxes.size());
    CHECK(std::count_if(object.volumes.begin(), object.volumes.end(),
                        [](const ModelVolume* v) { return v->type() == ModelVolumeType::MODEL_PART; }) == parts);
}
