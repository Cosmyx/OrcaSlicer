# feat/cosmyx-stealth-mode (PR #94)

## Purpose

Cosmyx builds must not reach the Orca or Bambu clouds by default: no cloud login, no profile sync, no online vendor
profile update, no HMS or device cloud services. Upstream already gates all of these on `AppConfig::get_stealth_mode()`,
but lets the user switch stealth mode off (setup guide, Preferences, "Quit Stealth Mode" button of the login dialog).
This branch makes stealth mode ON through one hook line at the getter, and makes the first-run setup guide finish
without showing the stealth-mode page and the Bambu network plugin page. Decisions 0070, 0071, 0072, 0073.

Important: this branch is the FIRST step. Its forced `return true;` is superseded by the stacked branch
`feat/cosmyx-cloud-server` (PR #109, decision 0200), which replaces that line with a policy that is "on until the user
opts out". Both must be rebased together and the final state of the line is the cloud-server one. The PR title is
"force stealth mode and skip the network plugin page".

## Parent and dependencies

- Parent: `DEV`. The range `origin/DEV..origin/feat/cosmyx-stealth-mode` also holds the foundation commits of PR #86
  (T0, not merged into DEV yet): `6cbd27d0fc`, `f3947e5550`, `ab1a545017`, `57866a96b9`, `5fbe728f6f`, `39c40f609f`.
  Feature commits are `37deb5c8c5`, `50f497e7cb`, `d5fd5834e3`, `aa48e1b4c0`.
- Child: `feat/cosmyx-cloud-server` (stacked, rewrites the AppConfig hook).
- Upstream APIs/keys/strings it relies on: `AppConfig::get_stealth_mode()`, config keys `firstguide/finish` and
  `stealth_mode`; every upstream reader of `get_stealth_mode()` (GUI_App.cpp login/sync/privacy/stealth blocked command
  sets, `HMS.cpp:43`, `MainFrame.cpp` login menu items, `Preferences.cpp` stealth checkbox and cloud tab,
  `WebViewDialog.cpp:789`, `PresetUpdater.cpp:1412` `check_vendor_update`, `PluginHostApp.cpp:122`); in
  `WebGuideDialog.cpp`: `GuideFrame::SaveProfileData()`, the member `StealthMode`, the JSON key `m_ProfileJson["stealth_mode"]`,
  `network_plugin_install` and `network_plugin_compability` profile keys (set from `installed_networking` and
  `is_compatibility_version()`); in `resources/web/guide/22/22.js` line 23, which reads `network_plugin_install != '1' ||
  (== '1' && network_plugin_compability == '0')` to decide Next versus Finish.

## Changes

| File | Kind | What the change does |
|---|---|---|
| `src/libslic3r/AppConfig.cpp` | upstream hook | Adds `    return true; // Cosmyx: stealth mode forced on (decision 0070)` as the FIRST statement of `bool AppConfig::get_stealth_mode()`, above the unchanged upstream body (`if (!get_bool("firstguide","finish")) return true; return get_bool("stealth_mode");`). One added line, upstream code after it becomes unreachable on purpose. |
| `src/slic3r/GUI/WebGuideDialog.cpp` | upstream hook | Include `#include "Cosmyx/logic/GuidePolicy.hpp" // Cosmyx` on line 2, right after `#include "WebGuideDialog.hpp"`; call `        Cosmyx::apply_guide_policy(m_ProfileJson, StealthMode); // Cosmyx` in `GuideFrame::SaveProfileData()`, immediately after `m_ProfileJson["stealth_mode"] = StealthMode;` (which follows `StealthMode = wxGetApp().app_config->get_bool("app","stealth_mode");`). |
| `src/slic3r/GUI/Cosmyx/logic/GuidePolicy.hpp` | Cosmyx-owned | Header-only, wxWidgets-free: `Cosmyx::apply_guide_policy(nlohmann::json& profile, bool& stealth)` sets `stealth = true`, `profile["stealth_mode"] = true`, `profile["network_plugin_install"] = "1"`, `profile["network_plugin_compability"] = "1"`. 22.js then keeps the Finish button and never leads to pages `4orca/` and `5/`. No guide page is edited and no download starts (the install only happens when page 5 sends `network_plugin_install` with yes). |
| `tests/cosmyx/test_cosmyx_stealth.cpp` | test | Getter and guide policy cases (see Verification). |
| `wiki/decisions/0070..0073-*.md` | data (docs) | 0070 forced at the getter; 0071 Preferences checkbox and "Quit Stealth Mode" button left visible (they write the ignored stored value); 0072 vendor updates blocked on purpose; 0073 guide policy. |
| `CHANGELOG.md` | data | Line under `<!-- cosmyx-slot: T7 -->` in `### GUI`. |
| Foundation (from #86) | Cosmyx-owned / CI / upstream hooks | Same files and hooks as in `feat-cosmyx-logs.md`: `include(Cosmyx/Cosmyx.cmake) # Cosmyx` in `src/libslic3r/CMakeLists.txt`, `include(GUI/Cosmyx/Cosmyx.cmake) # Cosmyx` in `src/slic3r/CMakeLists.txt`, `#include "Cosmyx/GCodeHooks.hpp" // Cosmyx` in `GCode.cpp`, include plus `Cosmyx::extend_print_config_def(*this); // Cosmyx` in `PrintConfig.cpp`, `add_subdirectory(cosmyx) # Cosmyx` in `tests/CMakeLists.txt`, plus `justfile`, `.github/workflows/cosmyx-checks.yml`, `scripts/cosmyx/*`, `tests/cosmyx/*`, decisions 0001-0004. |

## Rebase risk zones

| Upstream anchor | origin/DEV vs upstream/v2.5.1 | Upstream churn (DEV commits since 2026-01-01) |
|---|---|---|
| `src/libslic3r/AppConfig.cpp` `AppConfig::get_stealth_mode()` | function body identical in both (checked textually); file differs 2 added / 38 removed lines elsewhere | 81 |
| `src/slic3r/GUI/WebGuideDialog.cpp` (`SaveProfileData()`, line 1758-1759) | file identical in DEV and v2.5.1 (empty diff) | 29 |
| `resources/web/guide/22/22.js`, `4orca/`, `5/` | no diff | low |
| `get_stealth_mode()` readers (GUI_App.cpp, MainFrame.cpp, Preferences.cpp, HMS.cpp, WebViewDialog.cpp, PresetUpdater.cpp, PluginHostApp.cpp) | all present in v2.5.1 (GUI_App.cpp 9 hits, same set as DEV); GUI_App.cpp differs 22/38, Preferences.cpp 241/415 | GUI_App.cpp 246, Preferences.cpp 99 |
| Foundation hook files: `src/libslic3r/CMakeLists.txt`, `src/slic3r/CMakeLists.txt`, `GCode.cpp`, `PrintConfig.cpp`, `tests/CMakeLists.txt` | differ 7/24, 1/11, 147/269, 30/307, 3/5 | 127, 205, 342, 385, 9 |

The hook lines are inert to upstream changes elsewhere in those files; the risk is only the textual anchors moving.
`get_stealth_mode()` exists in v2.5.1 with the same shape.

## Intent to preserve

- Stealth mode is effectively ON for every reader, because they all go through the getter. The stored `stealth_mode`
  setting is still written by the guide, Preferences and the login dialog and is simply ignored (in this branch alone;
  `feat/cosmyx-cloud-server` later makes it user-controllable, with ON as the initial state).
- The setup guide must finish without the stealth page and the network plugin page, and without starting any plugin
  download. The guide policy only changes what the profile JSON reports.
- Zero-conflict rule: one added line in `AppConfig.cpp`, two in `WebGuideDialog.cpp`, nothing in guide pages.
- If upstream rewrites `get_stealth_mode()` (for example reads another key, or moves it to a header or a different
  class), do not force the old line: keep the intent by making the new getter return the Cosmyx policy as its first
  statement, in the new location. If upstream adds a reader that calls `get_bool("stealth_mode")` directly, it bypasses
  the hook; `git grep stealth_mode src` after the rebase finds them, and the right answer is a hook at that reader or a
  Cosmyx wrapper.
- If upstream changes `22.js` button logic or renames `network_plugin_install` / `network_plugin_compability`, update
  `GuidePolicy.hpp` to the new keys rather than editing the page. If `SaveProfileData()` is split or renamed, keep the
  call right where the profile JSON and the `StealthMode` member are finalised, before `SaveProfile()` persists them.

## Verification

- Catch2 (`cosmyx_tests`, tag `[cosmyx]`): "Stealth mode is on before the setup guide is finished", "Stealth mode stays on
  after the setup guide is finished" (this branch's forced-getter check, replaced by seeding cases on the cloud branch),
  "The guide policy forces stealth mode and skips the network plugin page", "The guide policy keeps an already stealth
  profile unchanged", and the foundation cases in `test_cosmyx_foundation.cpp`. Run `ctest -C Release -R cosmyx`.
- Script tests: `just test-scripts` (`scripts/cosmyx/tests/test_foundation.py`: changelog slots, justfile, decisions) and
  `just decisions`, run by the `Cosmyx checks` workflow on three OSes.
- Manual: fresh profile, run the setup guide to the end, expect no stealth page and no network plugin page; Preferences
  shows Stealth checked; login dialog cannot connect; no vendor update query on printer change.
- C++ is compiled and tested only in CI: `build_all.yml` via `workflow_dispatch` on the branch.

## Known pitfalls

- Hook-count tests: `feat/cosmyx-dark-default` also hooks `AppConfig.cpp`, so a test that counts every `// Cosmyx` line in that file breaks once both branches are merged. The cloud branch fixed its test to count only stealth lines (`ed15f92456`). Keep any such count scoped to its own feature.
- Foundation script tests count changelog slots: a new slot must be added to `SLOTS_BY_AREA` in `test_foundation.py`
  (the cloud branch had to add T18 there; the logs branch T12).
- Stacked history: the foundation is replayed in this range until #86 merges.

## Shared files with other branches

- `src/libslic3r/AppConfig.cpp`: also hooked by `feat/cosmyx-dark-default` (2 hook lines; include after the file's
  first lines). `feat/cosmyx-cloud-server` rewrites this branch's line and adds an include after `#include "AppConfig.hpp"`.
  Merge order matters: stealth-mode first, then cloud-server.
- `src/slic3r/GUI/WebGuideDialog.cpp`: only this branch (cloud-server's integration branch counts 2 `// Cosmyx` lines there,
  both from this branch).
- `src/slic3r/GUI/GUI_App.cpp`: not hooked here but by cloud-server, dark-default, install-paths, version; the line count
  in `ci/cosmyx-integration` is 12.
- `CHANGELOG.md` (slot T7, GUI area), `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md`,
  `wiki/decisions/README.md`, `justfile`, `.github/workflows/cosmyx-checks.yml`: shared with every branch.
- `src/slic3r/GUI/Cosmyx/logic/GuidePolicy.hpp` is edited again by `feat/cosmyx-cloud-server` (comment only).
