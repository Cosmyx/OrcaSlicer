# feat/cosmyx-machine-hook (PR #125)

Analysed commits: `origin/feat/cosmyx-models..origin/feat/cosmyx-machine-hook` (6 commits: `01c5600769`, `33bfc0edfa`, `b2d43d2094`, `d875c5cdd9`, `60caab89aa`, `72c6e3c6f6`). Compared with `origin/DEV` and `upstream/v2.5.2`.

## Purpose

The GUI learns whether the selected printer is a Cosmyx machine: its preset, or the system preset it inherits from, belongs to the Cosmyx printer bundle (vendor id `Cosmyx`, compared exactly; a custom printer with no system parent is not one). Cosmyx-only features read the flag when they build their UI and follow its flips each time the printer changes, the first preset load at startup included (decision 0222). Its first consumer is the "Cosmyx 3D Models" submenu of #92, now shown only on a Cosmyx machine (decision 0223). Changelog slots T28 and T29 (GUI).

## Parent and dependencies

- Parent: `feat/cosmyx-models` (PR #92), stacked: the gating of its submenu lives in this PR, and the integrate tool gives a branch a single parent (decision 0222).
- Children: `feat/cosmyx-printer-connection` (PR #127) uses `current_printer_is_cosmyx()`.
- Data dependency: the flag is only ever true with the Cosmyx vendor bundle (`feat/cosmyx-profiles`, PR #126, vendor id `Cosmyx`). Without it the models submenu never shows.
- Upstream APIs it relies on: `Tab::on_presets_changed()` with its `if (m_type == Preset::TYPE_PRINTER)` block calling `wxGetApp().switch_printer_agent()`, `PresetCollection::get_edited_preset_with_vendor_profile()`, `VendorProfile::id`, `wxGetApp().preset_bundle`.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `src/slic3r/GUI/Tab.cpp` | upstream hook | `#include "Cosmyx/CosmyxMachineHook.hpp" // Cosmyx` right after `#include "Tab.hpp"` (line 2; line 1 is a comment). In `Tab::on_presets_changed()`, inside the `TYPE_PRINTER` block, right after `wxGetApp().switch_printer_agent();`: `Cosmyx::notify_printer_changed(); // Cosmyx: Cosmyx machine flag (decision 0222)`. |
| `src/libslic3r/Cosmyx/CosmyxMachine.hpp`, `.cpp` | Cosmyx-owned | `COSMYX_VENDOR_ID`, `is_cosmyx_vendor()`, `is_cosmyx_printer(const PresetBundle&)`. |
| `src/slic3r/GUI/Cosmyx/logic/FlipNotifier.hpp`, `.cpp` | Cosmyx-owned | wxWidgets-free cached boolean, listeners called on the first value and each flip only. |
| `src/slic3r/GUI/Cosmyx/CosmyxMachineHook.hpp`, `.cpp` | Cosmyx-owned | `current_printer_is_cosmyx()`, `subscribe_printer_is_cosmyx()` / `unsubscribe_printer_is_cosmyx()`, `notify_printer_changed()`. |
| `src/slic3r/GUI/Cosmyx/CosmyxModelsMenu.hpp`, `.cpp`, `logic/MenuSlot.hpp`, `.cpp` | Cosmyx-owned (#92's files) | One slot per menu (anchor id, index, item id); the submenu is appended only on a Cosmyx machine, destroyed on a flip to false, rebuilt after "Add Handy models" (or at the saved index) on a flip to true; slots forgotten on the parent's `wxEVT_DESTROY`. Reuses #92's three `GUI_Factories.cpp` hooks, no new line there. |
| `tests/cosmyx/test_cosmyx_machine.cpp`, `test_cosmyx_flip_notifier.cpp`, `test_cosmyx_menu_slot.cpp` | test | Catch2 cases for vendor detection, the notifier and the slot position. |
| `scripts/cosmyx/tests/test_machine_hook.py`, `test_models_gating.py` | test | Pin the two `Tab.cpp` hook lines and their anchors, and the gating in the models menu. |
| `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md` | foundation data | T28 and T29 added to the GUI slot list. |
| `wiki/decisions/0222-cosmyx-machine-detection.md`, `0223-models-menu-cosmyx-only.md` | data (docs) | The decisions. |
| `CHANGELOG.md` | data (docs) | Two GUI lines under `<!-- cosmyx-slot: T28 -->` and `<!-- cosmyx-slot: T29 -->`, opened right after T11f. |

## Rebase risk zones

| Upstream file / function | In v2.5.2 | DEV vs v2.5.2 | Churn 2026 |
|--------------------------|-----------|---------------|-----------|
| `src/slic3r/GUI/Tab.cpp`, include block | `#include "Tab.hpp"` at line 2 | same line on DEV; 99 changed lines in the file | 424 commits on DEV |
| `src/slic3r/GUI/Tab.cpp`, `Tab::on_presets_changed()` | `wxGetApp().switch_printer_agent();` at line 2834 | same line on DEV | 424 commits on DEV |
| `src/slic3r/GUI/GUI_Factories.cpp` | #92's anchors | see the models sheet | see the models sheet |

The dry run onto `v2.5.2` replays the 6 commits cleanly.

## Intent to preserve

- One flag, read from the edited printer preset's vendor id, exactly `Cosmyx`; never the vendor name, never a translated label.
- The hook runs on every printer change, the first preset load at startup included: no second hook for startup.
- The models submenu shows once, right after "Add Handy models", only on a Cosmyx machine, and follows printer changes without leaking or duplicating items.

If upstream moves the printer-agent switch: keep `notify_printer_changed()` at the point where every printer preset change (startup included) passes, in the printer tab's preset-changed path. If `get_edited_preset_with_vendor_profile()` changes, adapt only `CosmyxMachine.cpp`.

## Verification

Catch2 `tests/cosmyx/test_cosmyx_machine.cpp`, `test_cosmyx_flip_notifier.cpp`, `test_cosmyx_menu_slot.cpp` (`ctest --test-dir build -C Release -R cosmyx --output-on-failure`); `just test-scripts` (hook pins, gating, slot list); `just decisions`. Manual: select a Cosmyx printer, right-click empty plate space ("Cosmyx 3D Models" present once), switch to another vendor's printer (gone), back to Cosmyx (back after "Add Handy models"). The context-menu GUI goldens change with this branch.

## Known pitfalls

- Subscribing does not call the listener: a consumer must read `current_printer_is_cosmyx()` when it builds its UI.
- Its `test_foundation.py` `SLOTS_BY_AREA["GUI"]` line is a one-line list, so every branch adding a GUI slot (dark-default, external-machines, update-check, printer-connection) conflicts textually there: keep the union of the slots.
- The branch sits on #92's older foundation; after the rebase it gains the later foundation commits like every child.

## Shared files with other branches

- `src/slic3r/GUI/Tab.cpp`: only this branch.
- `src/slic3r/GUI/Cosmyx/CosmyxModelsMenu.*`: #92's files, rewritten here; resolve to this branch's version on top of the rebased #92.
- `CHANGELOG.md` (slots T28, T29, right after T11f, like T24 and T26: keep every block, T24, T26, T28, T29, T31), `test_foundation.py` and decision 0003 (union of slots), `wiki/decisions` numbers 0222 and 0223.
