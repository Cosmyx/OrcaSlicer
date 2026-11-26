#include "CosmyxModelsMenu.hpp"

#include <cstddef>
#include <exception>
#include <iterator>
#include <map>
#include <set>
#include <string>
#include <vector>

#include <boost/filesystem/path.hpp>
#include <boost/log/trivial.hpp>

#include <wx/event.h>
#include <wx/menu.h>
#include <wx/menuitem.h>
#include <wx/string.h>
#include <wx/window.h>

#include "libslic3r/Format/ProjectStrategy.hpp"
#include "libslic3r/Format/bbs_3mf.hpp"
#include "libslic3r/Model.hpp"
#include "libslic3r/Preset.hpp"
#include "libslic3r/PresetBundle.hpp"
#include "libslic3r/PrintConfig.hpp"
#include "libslic3r/Utils.hpp"

#include "slic3r/GUI/GLCanvas3D.hpp"
#include "slic3r/GUI/GUI_App.hpp"
#include "slic3r/GUI/GUI_ObjectList.hpp"
#include "slic3r/GUI/I18N.hpp"
#include "slic3r/GUI/MsgDialog.hpp"
#include "slic3r/GUI/Plater.hpp"
#include "slic3r/GUI/Tab.hpp"
#include "slic3r/GUI/wxExtensions.hpp"

#include "CosmyxMachineHook.hpp"
#include "logic/CosmyxModels.hpp"
#include "logic/MenuSlot.hpp"

namespace Slic3r {
namespace GUI {
namespace Cosmyx {

namespace {

const char* const k_menu_icon = "menu_add_part_cosmyx";

boost::filesystem::path resource_path(const std::string& rel_path)
{
    // rel_path uses '/' separators, which boost::filesystem accepts on every OS.
    return boost::filesystem::path(Slic3r::resources_dir()) / boost::filesystem::path(rel_path);
}

DynamicPrintConfig& edited_print_config() { return wxGetApp().preset_bundle->prints.get_edited_preset().config; }

void refresh_print_tab()
{
    if (Tab* tab = wxGetApp().get_tab(Preset::TYPE_PRINT)) {
        tab->update_dirty();
        tab->reload_config();
    }
}

void suggest_zero_infill_direction()
{
    DynamicPrintConfig& config = edited_print_config();
    if (!needs_zero_infill_direction(config))
        return;

    const wxString msg_text = _L("This calibration model works best with infill directions set to 0 degrees. "
                                 "For optimal calibration results, it is advisable to set both 'Infill direction' "
                                 "and 'Solid infill direction' to 0.\n"
                                 "Yes - Change these settings automatically\n"
                                 "No  - Do not change these settings for me");
    MessageDialog dialog(wxGetApp().plater(), msg_text, _L("Calibration Suggestion"), wxICON_WARNING | wxYES | wxNO);
    if (dialog.ShowModal() == wxID_YES) {
        config.set_key_value("infill_direction", new ConfigOptionFloat(0.));
        config.set_key_value("solid_infill_direction", new ConfigOptionFloat(0.));
        refresh_print_tab();
    }
    wxGetApp().plater()->update();
}

void suggest_base_settings(const CalibrationPreset& preset)
{
    DynamicPrintConfig&            config = edited_print_config();
    const std::vector<std::string> keys   = differing_keys(preset.base, config);
    if (keys.empty())
        return;

    // The message names the three settings the shipped preset sets; a value
    // the preset leaves out is shown as it is in the print preset.
    auto value_of = [&](const char* key) -> const ConfigOption* {
        const ConfigOption* opt = preset.base.option(key);
        return opt != nullptr ? opt : config.option(key);
    };
    const ConfigOption* infill    = value_of("infill_direction");
    const ConfigOption* solid     = value_of("solid_infill_direction");
    const ConfigOption* one_wall  = value_of("only_one_wall_first_layer");
    const wxString      msg_text  = wxString::Format(
        _L("This calibration model works best with specific infill settings.\n"
           "For optimal calibration results, it is advisable to set:\n"
           "- Infill direction: %.0f°\n"
           "- Solid infill direction: %.0f°\n"
           "- Only one wall on first layer: %s\n\n"
           "Yes - Change these settings automatically\n"
           "No  - Do not change these settings for me"),
        infill != nullptr ? infill->getFloat() : 0., solid != nullptr ? solid->getFloat() : 0.,
        (one_wall != nullptr && one_wall->getBool()) ? "true" : "false");

    MessageDialog dialog(wxGetApp().plater(), msg_text, _L("Calibration Suggestion"), wxICON_WARNING | wxYES | wxNO);
    if (dialog.ShowModal() == wxID_YES) {
        config.apply_only(preset.base, keys);
        refresh_print_tab();
    }
}

// Replaces the modifiers of the objects that were just loaded, and only those:
// objects already on the plate keep theirs.
void apply_preset_to_loaded_objects(const CalibrationPreset& preset, const std::vector<size_t>& loaded)
{
    Plater* plater = wxGetApp().plater();
    Model&  model  = plater->model();
    std::vector<size_t> changed;
    for (size_t idx : loaded)
        if (idx < model.objects.size())
            changed.push_back(idx);
    if (changed.empty() || preset.boxes.empty())
        return;

    plater->take_snapshot("Add Cosmyx calibration modifiers");
    for (size_t idx : changed) {
        ModelObject& object = *model.objects[idx];
        apply_calibration_modifiers(object, preset);
        // Backup of the object mesh, as every Orca volume edit does.
        Slic3r::save_object_mesh(object);
        plater->changed_object(int(idx));
        wxGetApp().obj_list()->add_volumes_to_object_in_list(idx);
    }
    wxGetApp().obj_list()->update_selections();
    plater->get_view3D_canvas3D()->reload_scene(true);
    plater->update();
}

void load_model(const CosmyxModel& model)
{
    Plater* plater = wxGetApp().plater();
    if (plater == nullptr)
        return;

    const std::vector<boost::filesystem::path> files  = { resource_path(model.rel_path) };
    const std::vector<size_t>                  loaded = plater->load_files(files, LoadStrategy::LoadModel);
    if (loaded.empty())
        return;

    switch (model.action) {
    case ModelAction::Load: break;
    case ModelAction::SuggestZeroInfillDirection: wxGetApp().CallAfter([] { suggest_zero_infill_direction(); }); break;
    case ModelAction::ApplyCalibrationPreset: {
        const std::string preset_path = resource_path(model.preset_rel_path).string();
        wxGetApp().CallAfter([preset_path, loaded] {
            CalibrationPreset preset;
            try {
                preset = load_calibration_preset(preset_path);
            } catch (const std::exception& e) {
                BOOST_LOG_TRIVIAL(error) << "Cosmyx: " << e.what();
                return;
            }
            suggest_base_settings(preset);
            apply_preset_to_loaded_objects(preset, loaded);
        });
        break;
    }
    }
}

// Builds the "Cosmyx 3D Models" submenu into menu at insert_pos (wxNOT_FOUND:
// at the end) and returns its item. Every call takes a fresh id, so the
// update-UI handler bound for an older item never reaches the new one.
wxMenuItem* build_models_submenu(wxMenu* menu, wxWindow* parent, int insert_pos)
{
    auto* models_menu = new wxMenu;
    for (ModelGroup group : model_groups()) {
        auto* group_menu = new wxMenu;
        const std::vector<CosmyxModel>& models = cosmyx_models();
        for (size_t i = 0; i < models.size(); ++i) {
            if (models[i].group != group)
                continue;
            append_menu_item(group_menu, wxID_ANY, _(models[i].label), "",
                             [i](wxCommandEvent&) { load_model(cosmyx_models()[i]); }, "", menu);
        }
        append_submenu(models_menu, group_menu, wxID_ANY, _(group_label(group)), "", k_menu_icon,
                       []() { return true; }, parent);
    }
    return append_submenu(menu, models_menu, wxID_ANY, _(models_menu_label()), "", k_menu_icon,
                          []() { return true; }, parent, insert_pos);
}

// Where the submenu of one menu lives (decision 0223). The submenu is in the
// menu only while the selected printer is a Cosmyx machine; otherwise it is
// destroyed, and rebuilt right after its anchor when the printer flips back.
struct MenuSlot
{
    wxWindow*   parent      = nullptr;
    // Id of the item the submenu followed when appended ("Add Handy models"),
    // wxID_NONE for an empty menu. Ids come from wxNewId() and are never
    // reused, so a stale id matches no item.
    int         anchor_id   = wxID_NONE;
    // Index the submenu took when appended, used when the anchor is gone.
    std::size_t saved_index = 0;
    // Id of the submenu item while it is in the menu, wxID_NONE while hidden.
    int         item_id     = wxID_NONE;
};

std::map<wxMenu*, MenuSlot>& menu_slots()
{
    static std::map<wxMenu*, MenuSlot> slots;
    return slots;
}

void show_in_slot(wxMenu* menu, MenuSlot& slot)
{
    if (slot.item_id != wxID_NONE)
        return;
    std::vector<int> ids;
    for (wxMenuItem* item : menu->GetMenuItems())
        ids.push_back(item->GetId());
    const std::size_t pos = slot_insert_position(ids, slot.anchor_id, slot.saved_index);
    slot.item_id = build_models_submenu(menu, slot.parent, int(pos))->GetId();
}

void hide_slot(wxMenu* menu, MenuSlot& slot)
{
    if (slot.item_id == wxID_NONE)
        return;
    // Found by id, never by its translated label. Destroy() also deletes the
    // submenu.
    if (wxMenuItem* item = menu->FindChildItem(slot.item_id))
        menu->Destroy(item);
    slot.item_id = wxID_NONE;
}

void apply_printer_is_cosmyx(bool is_cosmyx)
{
    for (auto& [menu, slot] : menu_slots()) {
        if (is_cosmyx)
            show_in_slot(menu, slot);
        else
            hide_slot(menu, slot);
    }
}

// Subscribes once to the Cosmyx machine flag, and forgets the menus of a
// parent window when it is destroyed: the menus are MenuFactory members,
// which die with the plater inside that window, so a later printer change
// must not reach them.
void track(wxWindow* parent)
{
    static bool subscribed = false;
    if (!subscribed) {
        subscribed = true;
        subscribe_printer_is_cosmyx(apply_printer_is_cosmyx);
    }
    if (parent == nullptr)
        return;
    static std::set<wxWindow*> watched;
    if (!watched.insert(parent).second)
        return;
    parent->Bind(wxEVT_DESTROY, [parent](wxWindowDestroyEvent& evt) {
        if (evt.GetEventObject() == parent) {
            auto& slots = menu_slots();
            for (auto it = slots.begin(); it != slots.end();)
                it = it->second.parent == parent ? slots.erase(it) : std::next(it);
            watched.erase(parent);
        }
        evt.Skip();
    });
}

} // namespace

void append_models_submenu(wxMenu* menu, wxWindow* parent)
{
    if (menu == nullptr)
        return;
    track(parent);

    // Idempotence: drop the item a previous call added to this menu (see
    // MenuFactory::update_default_menu), then take the slot again after the
    // item appended just before this call.
    auto& slots = menu_slots();
    if (const auto it = slots.find(menu); it != slots.end()) {
        hide_slot(menu, it->second);
        slots.erase(it);
    }

    MenuSlot slot;
    slot.parent      = parent;
    slot.saved_index = menu->GetMenuItemCount();
    if (slot.saved_index > 0)
        slot.anchor_id = menu->FindItemByPosition(slot.saved_index - 1)->GetId();
    // Hidden from the start on a printer that is not a Cosmyx machine; the
    // first preset load at startup then confirms or flips it.
    if (current_printer_is_cosmyx())
        slot.item_id = build_models_submenu(menu, parent, wxNOT_FOUND)->GetId();
    slots[menu] = slot;
}

} // namespace Cosmyx
} // namespace GUI
} // namespace Slic3r
