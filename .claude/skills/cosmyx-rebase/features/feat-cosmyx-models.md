# feat/cosmyx-models (PR #92)

## Purpose

Adds a top-level "Cosmyx 3D Models" submenu to the empty-space (default) context menu and the plate context menu, next to "Add Handy models". Groups: "Calibration Models Dual Head" (Calage 1, 2 and 3 SNDT, Cube Bicolore), "Calibration Models Single Head" (Cosmyx Calage 1 Nova, Cosmyx Cube) and "Cosmyx Handy Models" (belt tension control, spool holder). Calage 1 offers to set the print preset's infill directions to 0 degrees; Calage 3 offers its base print settings and replaces the modifiers of the objects it just loaded (only those) with the boxes of a JSON calibration preset. Restores the models of the earlier Cosmyx branch (tag `cosmyx-2.3.1-7`) with portable file names. Decisions: 0050 to 0055. Changelog slot: T5 (GUI).

## Parent and dependencies

- Parent: `DEV`. Carries foundation commits `6cbd27d0fc`..`39c40f609f` (PR #86). Own commits: `c80ccd6af2` (feature), `48351460f0` (tests), `91f388914d` (docs), `662b5d79fa` (unknown option refusal fix).
- No dependency on other feature branches. Uses the foundation GUI module (`src/slic3r/GUI/Cosmyx/Cosmyx.cmake`, glob of the folder and `logic/`).
- Upstream symbols used: `MenuFactory::create_default_menu()`, `create_plate_menu()`, `update_default_menu()` (rebuilds the default menu in place), `append_submenu`, `append_menu_item` (`wxExtensions.hpp`), `Plater::load_files(files, LoadStrategy, ...)` returning loaded object indices, `LoadStrategy::LoadModel`, `Plater::take_snapshot`, `changed_object`, `get_view3D_canvas3D()`, `ObjectList::add_volumes_to_object_in_list`, `update_selections`, `MessageDialog`, `Tab::update_dirty`/`reload_config`, `preset_bundle->prints.get_edited_preset()`, `resources_dir()`, `Model::read_from_file`, `ModelObject`/`ModelVolume`, `DynamicPrintConfig::set_deserialize_strict`, icon loader (`resources/images/<name>.svg`).

## Changes

| File | Kind | What it does |
|---|---|---|
| `src/slic3r/GUI/GUI_Factories.cpp` | upstream hook | Line 2 (after `#include "libslic3r/Config.hpp"`): `#include "Cosmyx/CosmyxModelsMenu.hpp" // Cosmyx`. In `MenuFactory::create_default_menu()`, right after `append_submenu(&m_default_menu, sub_menu_handy, wxID_ANY, _L("Add Handy models"), "", "menu_add_part", []() {return true; }, m_parent);`: `Cosmyx::append_models_submenu(&m_default_menu, m_parent); // Cosmyx`. In `MenuFactory::create_plate_menu()`, right after the same "Add Handy models" `append_submenu(menu, sub_menu_handy, ...)`: `Cosmyx::append_models_submenu(menu, m_parent); // Cosmyx`. |
| `src/slic3r/GUI/Cosmyx/CosmyxModelsMenu.hpp/.cpp` | Cosmyx-owned | `append_models_submenu(wxMenu*, wxWindow* parent)`: builds the submenu, idempotent (remembers the id of the item it appended per menu, destroys it first, new id each time), so `update_default_menu()` needs no hook. Handles load, infill suggestion dialog and calibration preset flow with one undo snapshot. |
| `src/slic3r/GUI/Cosmyx/logic/CosmyxModels.hpp/.cpp` | Cosmyx-owned | wxWidgets-free catalogue (`ModelGroup`, `ModelAction`, `cosmyx_models()`), `parse_calibration_preset()` (rejects malformed input and unknown options), `make_modifier_mesh()`, `needs_zero_infill_direction()`, `differing_keys()`, `apply_calibration_modifiers()`. Compiled into `libslic3r_gui` and `cosmyx_tests`. |
| `src/slic3r/GUI/Cosmyx/{Cosmyx.cmake,Cosmyx.hpp,logic/.gitkeep}` | Cosmyx-owned (foundation) | Glob of the module. |
| `resources/cosmyx/models/*.3mf,*.stl`, `resources/cosmyx/models/calibration/*.3mf` | data | Eight model files copied byte for byte from `cosmyx-2.3.1-7`, lowercase names with underscores. |
| `resources/cosmyx/calibration/calage_3_modifiers.json` | data | Calage 3 base settings (`infill_direction` 90, `solid_infill_direction` 90, `only_one_wall_first_layer`) and one region (name, position, size, rotation, own settings). |
| `resources/images/menu_add_part_cosmyx.svg` | data (new file in an upstream folder) | Menu icon, must stay in `resources/images/` because the loader only looks there. |
| `src/libslic3r/CMakeLists.txt`, `src/slic3r/CMakeLists.txt`, `tests/CMakeLists.txt`, `src/libslic3r/PrintConfig.cpp`, `src/libslic3r/GCode.cpp` | upstream hook (foundation) | Identical foundation hooks, all tagged `Cosmyx` (see the sibling docs). |
| `tests/cosmyx/test_cosmyx_models.cpp` | test | 10 cases (see Verification). |
| `wiki/decisions/0050..0055` | docs | |
| `CHANGELOG.md`, `justfile`, `scripts/cosmyx/*`, `.github/workflows/cosmyx-checks.yml` | CI / docs (foundation) | Line under slot T5. |

## Rebase risk zones

Hook patch applies cleanly on the `upstream/v2.5.1` tree (`git apply --check`). Anchors in the tag: `Add Handy models` appended at `GUI_Factories.cpp` lines 1715 (default menu) and 2080 (plate menu), vs 1741 and 2127 in DEV; `update_default_menu` still destroys items by the labels `Add Primitive`, `Add Handy models`, `Show Labels` (line 2807). DEV vs tag: `GUI_Factories.cpp` +7/-62 (DEV adds code elsewhere); 78 commits since 2026-01-01 on DEV. `resources/images/` and `resources/cosmyx/` are new, no conflict possible. Upstream APIs checked present in the tag: `Plater::load_files` (returns `std::vector<size_t>`, `LoadStrategy` default `LoadModel | LoadConfig`), `append_submenu` in `wxExtensions.hpp`, `take_snapshot`, `GUI_ObjectList.hpp`, `MsgDialog.hpp`, `Format/ProjectStrategy.hpp`, `Format/bbs_3mf.hpp`. The 3 hook lines are the only upstream edits.

## Intent to preserve

- The "Cosmyx 3D Models" menu (icon `menu_add_part_cosmyx`, on every OS, no platform check) appears at the top level of the empty-space and plate context menus, right after "Add Handy models", exactly once even after `update_default_menu()` rebuilds the menu. Items are found by id, never by translated label.
- Labels (msgids) stay as in decision 0055 so existing translations apply.
- Calage 3: modifiers are replaced only on objects returned by `load_files` for this load; other objects are untouched; one undo snapshot; boxes are rotated about X, Y then Z and translated in the rotated frame; negative size components give outward facing facets; base settings are offered in a yes/no dialog and only differing keys are applied.
- Calibration preset refuses unknown option keys (names the key).
- If upstream restructures the context menus (for example the menu is built elsewhere or `update_default_menu` is replaced), keep calling `append_models_submenu(menu, parent)` once per built menu after the handy models entry and keep the function idempotent; do not move logic into upstream files. If `Plater::load_files` changes its return type, adapt only `CosmyxModelsMenu.cpp`. Command palette entries stay absent (decision 0053).

## Verification

Catch2 `tests/cosmyx/test_cosmyx_models.cpp` (tag `[cosmyx]`): "Every Cosmyx model is shipped under a portable path", "Every Cosmyx group has models and a label", "Every Cosmyx model file loads", "The shipped Calage 3 preset parses", "A malformed calibration preset is refused", "A modifier box mesh keeps the original placement and faces outwards", "The zero infill direction suggestion triggers on any non-zero direction", "Only the preset settings that differ are reported", "Calibration modifiers replace only the modifiers of the given object", "Calibration modifiers apply to the shipped Calage 3 model". Foundation `[cosmyx]` cases and `just test-scripts`. Run `ctest --test-dir build -C Release -R cosmyx`; GUI compile proof is the `build_all.yml` run on the branch. Manual (and future GUI golden): right-click empty plate space, "Cosmyx 3D Models" present once; load Calage 3 SNDT with another object on the plate, check only the new object gets the modifier box; open and close the menu after a preset change to ensure no duplicate item.

## Known pitfalls

- `662b5d79fa`: `set_deserialize_strict()` does not reject an unknown key: the upstream legacy-name pass clears unknown keys and only records them in the substitution context, so a typo in a preset was dropped silently. `set_option()` now passes its own substitution context and throws, naming the key, when the key is recorded as unrecognized.
- Do not call `ModelObject::delete_volume()` to clear old modifiers: it folds the last volume's transform into the instances and moves the frame the boxes use (decision 0052).
- `update_default_menu()` rebuilds in place: a plain append would duplicate the item (decision 0050).
- Keep model file names lowercase, with no spaces; a test checks every catalogue path. Binary `.3mf`/`.stl` and the SVG are assets and must keep their byte content (LF normalisation must not touch them; check `.gitattributes` treats them as binary).
- New GUI sources must be listed for translation extraction: decision 0055 notes `src/slic3r/GUI/Cosmyx/` must be in the extraction (`localization/i18n/list.txt` is an upstream-owned file; the translation task handles it).

## Shared files with other branches

- Foundation commits and stubs shared with all siblings. This branch adds no libslic3r Cosmyx source; its stubs there (`BedTemperatureOff.*`, `ChtNozzle.cpp`, `IroningTemperature.*`) are the foundation versions.
- `src/slic3r/GUI/Cosmyx/Cosmyx.hpp` and `Cosmyx.cmake` are foundation files; this branch deliberately does not edit `Cosmyx.hpp` (decision 0050), so other GUI branches never collide there. Future GUI branches (T6, T7, T11b..f slots) add their own files in the same folder through the glob.
- `GUI_Factories.cpp` is only edited here. `CHANGELOG.md` slot T5, `wiki/decisions` 0050-0059, `tests/cosmyx/CMakeLists.txt` globs GUI `logic/*.cpp` (any other branch adding `logic/` files is compiled into `cosmyx_tests` too).
