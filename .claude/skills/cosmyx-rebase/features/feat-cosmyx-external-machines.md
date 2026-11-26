# feat/cosmyx-external-machines (PR #121)

Analysed commits: `origin/chore/cosmyx-foundation..origin/feat/cosmyx-external-machines` (2 commits: `46557636cd`, `b3cef1ff2a`). Compared with `origin/DEV` and `upstream/v2.5.2`.

## Purpose

Cosmyx neither tests nor supports the Bambu Lab cloud and network plug-in, nor the machines they drive, and users must know that before turning one on. The Online tab of Preferences therefore gathers "Enable Bambu Cloud" and "Enable Bambu network plug-in" (with the plug-in version selector) in one "External machines" section (French "Machines externes"), and turning either toggle on asks for confirmation first; Cancel leaves it off, turning one off never asks (decision 0219).

## Parent and dependencies

- Parent: `chore/cosmyx-foundation` (PR #86): slot T24 in `SLOTS_BY_AREA["GUI"]` and decision 0003.
- Translations (`feat/cosmyx-translations`, PR #95): strings in `localization/cosmyx/external-machines/` (French translated, other languages left to the per-language pass; "Enable" is an OrcaSlicer string and stays out of the template).
- Upstream APIs it relies on: the shape `PreferencesDialog::create_items()` gives the Online tab (a row is a sizer holding a `CheckBox`, a title is a sizer holding a `StaticLine`), the local variables `g_sizer`, `item_bambu_cloud`, `item_enable_plugin`, `item_plugin_version`, `wxEVT_TOGGLEBUTTON` on `CheckBox`, `MessageDialog`.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `src/slic3r/GUI/Cosmyx/ExternalMachinesPrefs.hpp`, `.cpp` | Cosmyx-owned | `setup_external_machines(g_sizer, item_bambu_cloud, item_enable_plugin)`: renames the "Bambu network plug-in" title to "External machines", moves the Bambu Cloud row into it above the plug-in toggle, destroys the "Cloud Providers" title when that row was its only one, binds a second toggle handler (runs first) that shows the warning. Logs a warning and leaves the layout alone when the expected shape is not found. |
| `src/slic3r/GUI/Cosmyx/logic/ExternalMachines.hpp`, `.cpp` | Cosmyx-owned | Pure rule `external_toggle_outcome()` (on + Enable passes, on + Cancel reverts, off never asks). |
| `src/slic3r/GUI/Preferences.cpp` | upstream hook | `#include "Cosmyx/ExternalMachinesPrefs.hpp" // Cosmyx` after `#include "DownloadProgressDialog.hpp"` (last include before `#ifdef __WINDOWS__`). In `create_items()`: `Cosmyx::setup_external_machines(g_sizer, item_bambu_cloud, item_enable_plugin); // Cosmyx: External machines section (decision 0219)` right after `g_sizer->Add(item_plugin_version);`. |
| `tests/cosmyx/test_cosmyx_external_machines.cpp` | test | Catch2 cases for `external_toggle_outcome()`. |
| `scripts/cosmyx/tests/test_external_machines.py` | test | Pins the two hook lines and their anchors. |
| `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md` | foundation data | T24 added to the GUI slot list. |
| `localization/cosmyx/external-machines/` | data | `messages.pot` and 22 `.po` files. |
| `wiki/decisions/0219-external-machines-section.md` | data (docs) | The decision. |
| `CHANGELOG.md` | data (docs) | One GUI line under `<!-- cosmyx-slot: T24 -->`, opened right after T11f. |

## Rebase risk zones

| Upstream file / function | In v2.5.2 | DEV vs v2.5.2 | Churn 2026 |
|--------------------------|-----------|---------------|-----------|
| `src/slic3r/GUI/Preferences.cpp`, include block | `#include "DownloadProgressDialog.hpp"` at line 74 | 415 insertions, 241 deletions in the file | 99 |
| `src/slic3r/GUI/Preferences.cpp`, `create_items()` Online tab | `item_bambu_cloud` (line 2233), `item_enable_plugin` (2268), `g_sizer->Add(item_plugin_version);` (2272) all present | same names on DEV (2468, 2503) | 99 |

## Intent to preserve

- Both Bambu toggles sit together under "External machines", above the plug-in version selector; no orphan "Cloud Providers" title.
- Every upstream behaviour of the rows stays (stealth mode disabling Bambu Cloud, plug-in install prompt, restart prompts): the rows are moved, never re-created.
- Turning a toggle on asks first and Cancel writes nothing; a setting already on shows on without a warning.

If upstream rewrote the hooked code: keep the call after the last of the two rows and the version row is built, passing the same three sizers. If the rows are renamed, nothing changes. If their sizer shape changes, the helper logs a warning and leaves the layout; adapt the shape reading in `ExternalMachinesPrefs.cpp`, not the hook.

## Verification

Catch2 `tests/cosmyx/test_cosmyx_external_machines.cpp` (`ctest --test-dir build -C Release -R cosmyx --output-on-failure`); `just test-scripts` (hook pins, slot list); `just decisions`. Manual: open Preferences > Online, check the section, tick each toggle (warning, Cancel leaves it off, Enable keeps upstream's flow), untick (no prompt). The GUI golden of the Online tab changes with this branch.

## Known pitfalls

- The Online tab golden of `test/cosmyx-gui-goldens` must be regenerated once both are merged.
- Two hook lines asserted by `test_external_machines.py`: a moved anchor fails the script tests, not the build.

## Shared files with other branches

- `src/slic3r/GUI/Preferences.cpp`: also `feat/cosmyx-cloud-server` (include on line 2, panel after `g_sizer->Add(item_network_test)`). Different anchors; integration total 4 `Cosmyx` lines.
- `CHANGELOG.md` (slot T24, right after T11f, like update-check's T26), `test_foundation.py` and decision 0003 (union of slots), `wiki/decisions` number 0219.
