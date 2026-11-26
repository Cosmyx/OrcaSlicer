# feat/cosmyx-printer-connection (PR #127)

Analysed commits: `origin/feat/cosmyx-machine-hook..origin/feat/cosmyx-printer-connection` (5 commits: `6690f2e105`, `c431de2820`, `dd514815b7`, `c55e65d8a1`, `d94f7c9a94`). Compared with `origin/DEV` and `upstream/v2.5.2`.

## Purpose

On a Cosmyx printer, the "Connection" button of the printer title bar opens a Cosmyx physical printer dialog instead of upstream's generic one. Its "Setup" tab asks only for the preset name, the machine IP or host name (optional port) and the API key, saves the OctoPrint address, the machine web interface and the key into the printer preset, and tests the connection. Its "Machine information" tab, enabled once the settings are saved and a connection test succeeded, reads the model, serial number, versions, installed options, hot ends and camera from the machine (`/api/machine/*`, `/api/camera`). Other printers keep the generic dialog (decision 0225). Changelog slot T31 (GUI).

## Parent and dependencies

- Parent: `feat/cosmyx-machine-hook` (PR #125), stacked: `show_cosmyx_printer_dialog()` returns false unless `current_printer_is_cosmyx()` (decision 0222) is true.
- Translations (`feat/cosmyx-translations`, PR #95): strings in `localization/cosmyx/printer-connection/` (46 msgids; French translated, other languages empty, left to the per-language pass).
- Data dependency: only reachable with the Cosmyx vendor bundle (`feat/cosmyx-profiles`, PR #126).
- Upstream APIs it relies on: `Sidebar::Sidebar()` building `p->m_printer_connect` and binding its `wxEVT_BUTTON` handler, `PhysicalPrinterDialog`, `DPIDialog`, Orca `Button`, `Tab::save_preset("", false, false, true, name)`, `check_preset_name()`, `PrintHost::test()` (OctoPrint host), `Http`, `wxGetApp().CallAfter`, nlohmann::json.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `src/slic3r/GUI/Plater.cpp` | upstream hook | `#include "Cosmyx/CosmyxPrinterConnectionDialog.hpp" // Cosmyx` right after `#include "Plater.hpp"` (line 2). First statement of the `m_printer_connect` `wxEVT_BUTTON` handler: `if (Cosmyx::show_cosmyx_printer_dialog(this->GetParent())) return; // Cosmyx`. The second `PhysicalPrinterDialog` in `Sidebar` (the edit button, about 140 lines later) is not hooked. |
| `src/slic3r/GUI/Cosmyx/CosmyxPrinterConnectionDialog.hpp`, `.cpp` | Cosmyx-owned | The dialog: two-button tab strip over a `wxSimplebook`, Apply / OK / Cancel, background requests on detached threads guarded by an alive flag and a generation counter. |
| `src/slic3r/GUI/Cosmyx/logic/CosmyxPrinterConnection.hpp`, `.cpp` | Cosmyx-owned | wxWidgets-free host check, URL builders and parser, saved values, unlock rule, failure classification. |
| `src/slic3r/GUI/Cosmyx/logic/CosmyxPrinterConnectionInfo.hpp`, `.cpp` | Cosmyx-owned | Tolerant readers of the four machine answers. |
| `tests/cosmyx/test_cosmyx_printer_connection.cpp`, `test_cosmyx_printer_connection_info.cpp` | test | Catch2 cases for the logic and the readers. |
| `scripts/cosmyx/tests/test_printer_connection_hook.py` | test | Pins the two `Plater.cpp` hook lines and their anchors. |
| `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md` | foundation data | T31 added to the GUI slot list. |
| `localization/cosmyx/printer-connection/` | data | `messages.pot` and 22 `.po` files. |
| `wiki/decisions/0225-cosmyx-printer-connection-dialog.md` | data (docs) | The decision. |
| `CHANGELOG.md` | data (docs) | One GUI line under `<!-- cosmyx-slot: T31 -->`, right after T29. |

## Rebase risk zones

| Upstream file / function | In v2.5.2 | DEV vs v2.5.2 | Churn 2026 |
|--------------------------|-----------|---------------|-----------|
| `src/slic3r/GUI/Plater.cpp`, include block | `#include "Plater.hpp"` at line 1, followed by `../Utils/NetworkAgent.hpp` | DEV adds `#include "LazyPage.hpp"` at line 2, right under the hook's include | 562 commits on DEV |
| `src/slic3r/GUI/Plater.cpp`, `m_printer_connect` handler in `Sidebar::Sidebar()` | `Bind` at line 2844, `PhysicalPrinterDialog dlg(...)` at 2845 | 2854/2855 on DEV; 897 changed lines in the file | 562 commits on DEV |

The dry run onto `v2.5.2` stops on `Plater.cpp` (`6690f2e105`): the include's context line `LazyPage.hpp` does not exist there. Resolution: the hook include right after `#include "Plater.hpp"`, upstream's include block otherwise unchanged; the handler line applies as is.

## Intent to preserve

- Non-Cosmyx printers see upstream's `PhysicalPrinterDialog` unchanged; the hook returns before it only when the Cosmyx dialog was shown.
- The connection test never changes the preset (runs on a copy of the edited config); the UI thread never blocks; closing the dialog drops late answers.
- The information tab unlocks only when the saved preset holds a connection and the last successful test checked that same host and key.

If upstream rewrites the title bar or the button: keep the one-line early return as the first statement of whatever opens the physical printer dialog from the printer title bar. If `Tab::save_preset` or `PrintHost::test` change, adapt only `CosmyxPrinterConnectionDialog.cpp`.

## Verification

Catch2 `tests/cosmyx/test_cosmyx_printer_connection.cpp`, `test_cosmyx_printer_connection_info.cpp` (`ctest --test-dir build -C Release -R cosmyx --output-on-failure`); `just test-scripts` (hook pins, slot list); `just decisions`; `msgfmt --check-format` on the catalogue. GUI compile proof is the dev build of the branch. Manual: on a Cosmyx printer press "Connection" (Cosmyx dialog), fill and Apply (test runs, information tab unlocks), on another printer (generic dialog). Goldens still to add: Setup empty, Setup filled, Information greyed, Information filled (mocked HTTP).

## Known pitfalls

- `test_foundation.py` `SLOTS_BY_AREA["GUI"]` and decision 0003's GUI line are one-line lists: every branch adding a GUI slot conflicts there textually; keep the union.
- 46 msgids are in French only: the other 21 languages need a translation pass, never filled during a rebase.

## Shared files with other branches

- `src/slic3r/GUI/Plater.cpp`: only this branch.
- `CHANGELOG.md` (slot T31, right after T29), `test_foundation.py` and decision 0003 (union of slots), `wiki/decisions` number 0225.
