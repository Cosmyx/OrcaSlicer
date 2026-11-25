#ifndef slic3r_GUI_Cosmyx_CosmyxModels_hpp_
#define slic3r_GUI_Cosmyx_CosmyxModels_hpp_

// Catalogue of the Cosmyx 3D models shipped under <resources>/cosmyx/models and
// the wxWidgets-free logic behind their menu: the calibration preset file
// (base print settings plus modifier boxes) and how it is applied to a model
// object. The menu itself lives in ../CosmyxModelsMenu.cpp.
//
// This file links with libslic3r only: it is compiled into libslic3r_gui and
// into cosmyx_tests.

#include <string>
#include <vector>

#include "libslic3r/Point.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "libslic3r/TriangleMesh.hpp"

namespace Slic3r {
class ModelObject;
namespace GUI {
namespace Cosmyx {

// Submenus of the "Cosmyx 3D Models" menu, in display order.
enum class ModelGroup
{
    DualHead,
    SingleHead,
    Handy,
};

// What the menu does once the model files are loaded.
enum class ModelAction
{
    // Load only.
    Load,
    // Offer to set the infill directions of the print preset to 0 degrees.
    SuggestZeroInfillDirection,
    // Offer the preset's base print settings, then replace the modifiers of
    // the loaded objects with the preset's boxes.
    ApplyCalibrationPreset,
};

struct CosmyxModel
{
    // Stable identifier, never shown.
    std::string key;
    ModelGroup  group;
    // English label, marked with L(); translated by the menu.
    const char* label;
    // Model file, relative to the resources folder, with '/' separators.
    std::string rel_path;
    ModelAction action;
    // Calibration preset (JSON), relative to the resources folder; only for
    // ModelAction::ApplyCalibrationPreset.
    std::string preset_rel_path;
};

// Label of the top-level menu item.
const char* models_menu_label();

// Label of a group submenu.
const char* group_label(ModelGroup group);

// Every group, in display order.
const std::vector<ModelGroup>& model_groups();

// Every model, grouped and in display order inside each group.
const std::vector<CosmyxModel>& cosmyx_models();

// A modifier box of a calibration preset. The box is a cube of `size`
// (a negative component extends the box towards negative coordinates), rotated
// about X, then Y, then Z by `rotation_deg`, with `position` applied in the
// rotated frame, as the original Cosmyx menu did.
struct ModifierBox
{
    std::string        name;
    Vec3d              position{ Vec3d::Zero() };
    Vec3d              size{ Vec3d::Zero() };
    Vec3d              rotation_deg{ Vec3d::Zero() };
    // Settings of the modifier volume.
    DynamicPrintConfig config;
};

struct CalibrationPreset
{
    // Print settings the model expects in the print preset.
    DynamicPrintConfig       base;
    std::vector<ModifierBox> boxes;
};

// Parses a calibration preset:
//   { "base_settings": { <print option>: <value>, ... },
//     "regions": [ { "name": "...", "position": [x,y,z], "size": [x,y,z],
//                    "rotation": [x,y,z], <print option>: <value>, ... } ] }
// Every other key is a print option, checked against the print config
// definition. Throws std::runtime_error on malformed input or an unknown option.
CalibrationPreset parse_calibration_preset(const std::string& json_text);

// Reads and parses a calibration preset file. Throws std::runtime_error.
CalibrationPreset load_calibration_preset(const std::string& path);

// Mesh of a modifier box, in the object's coordinates. Its facets always face
// outwards, whatever the sign of the size components.
TriangleMesh make_modifier_mesh(const ModifierBox& box);

// True when the print config has a non-zero infill or solid infill direction.
bool needs_zero_infill_direction(const DynamicPrintConfig& config);

// Keys of `wanted` whose value is missing from, or differs in, `current`.
std::vector<std::string> differing_keys(const DynamicPrintConfig& wanted, const DynamicPrintConfig& current);

// Removes the parameter modifiers of the object and adds one modifier volume
// per box of the preset. Model parts and other volumes are left untouched.
// Returns the number of modifiers added.
size_t apply_calibration_modifiers(ModelObject& object, const CalibrationPreset& preset);

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r

#endif // slic3r_GUI_Cosmyx_CosmyxModels_hpp_
