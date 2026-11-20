# feat/cosmyx-dark-default (PR #98)

Analysed commits: `origin/feat/cosmyx-version..origin/feat/cosmyx-dark-default` (4 commits: `36eb2095ea`, `2c89624ef6`, `4cbcfab4fa`, `b93fce0559`). Compared with `origin/DEV` and `upstream/v2.5.1`.

## Purpose

The Cosmyx build must look different from OrcaSlicer at first sight, so the application always runs in dark mode on Windows, macOS and Linux, for fresh installs and for existing configs, whatever the system appearance says. There is no way back to light (decision 0136): no setting, no config key, no Preferences item. The Windows Preferences "Enable dark Mode" toggle is left visible but inert (decision 0139).

The policy has two halves:

- libslic3r half (decision 0137): `dark_color_mode` in the app config is pinned to `"1"`. About ten upstream places read that key directly instead of calling `GUI_App::dark_mode()`.
- GUI half (decision 0138): `GUI_App::dark_mode()` returns true at once, heals the key, and on macOS and Linux asks wxWidgets once for the dark native appearance (`wxApp::SetAppearance(Dark)`). Windows already gets native dark from upstream NppDarkMode, driven by `dark_mode()`, so `SetAppearance` is skipped there (the only `#ifndef _WIN32` exception, confined to `ColorMode.cpp`).

## Parent and dependencies

- Parent: `feat/cosmyx-version` (PR #93). Real code dependency on it: only through the shared stack (`GUI_App.cpp` line 2 holds the version include, this branch adds line 3) and the foundation (T0, PR #86). No code of this feature calls the version feature.
- `test/cosmyx-gui-goldens` carries copies of these four commits (different shas: `6ec695e6a7`, `27a82384fa`, `d69a7266dc`, `cd33db00d3`), because the goldens need dark mode. After both merge the content is identical; expect a clean no-op during rebase.
- Upstream APIs, classes and keys it uses: `AppConfig::get/set`, `AppConfig::set_defaults()`, config key `dark_color_mode`, `GUI_App::dark_mode()`, `wxGetApp().app_config`, `SUPPORT_DARK_MODE`, `wxTheApp`, `wxApp::SetAppearance`, `wxApp::Appearance::Dark`, `wxApp::AppearanceResult`, `wxIsMainThread`. wxWidgets must be the fork build (wxWidgets 3.3 with `SetAppearance`; deps pin `b44c39c100975a0ac0e46f937aa3f3eae5e18631` at the time of the decision).

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `src/libslic3r/Cosmyx/ColorModeDefault.hpp`, `.cpp` | Cosmyx-owned | `forced_dark_color_mode = "1"`; `bool force_dark_color_mode(AppConfig&)` sets the key to `"1"` whatever it holds and returns true when it changed. wxWidgets-free. |
| `src/slic3r/GUI/Cosmyx/ColorMode.hpp`, `.cpp` | Cosmyx-owned | `bool force_dark_mode()`: heals the config key through the libslic3r function (if `wxTheApp` and `app_config` exist), on non-Windows calls `apply_native_dark_appearance()` once from the main thread (logs a warning if the result is not Ok), always returns true. |
| `src/libslic3r/AppConfig.cpp` | upstream hook | Line 2: `#include "Cosmyx/ColorModeDefault.hpp" // Cosmyx` (after `#include "Technologies.hpp"`). In `AppConfig::set_defaults()`: `Cosmyx::force_dark_color_mode(*this); // Cosmyx` placed right after the `if (get("show_center_of_mass").empty()) set_bool("show_center_of_mass", false);` block and before the `#ifdef _WIN32` block (which holds upstream's `if (get("dark_color_mode").empty()) set("dark_color_mode", "0");`). Outside the `#ifdef` so every OS is covered. |
| `src/slic3r/GUI/GUI_App.cpp` | upstream hook | Line 3: `#include "Cosmyx/ColorMode.hpp" // Cosmyx` (after the version include `Cosmyx/logic/CosmyxVersion.hpp`). In `bool GUI_App::dark_mode()`: `if (Cosmyx::force_dark_mode()) return true; // Cosmyx` as the first line after `#ifdef SUPPORT_DARK_MODE` (before `#if __APPLE__`). The upstream body stays below, unreached. |
| `tests/cosmyx/test_color_mode.cpp` | test | Catch2 cases listed under Verification. |
| `wiki/decisions/0136` to `0139` | data (docs) | Always on; pinned key; native appearance; inert Windows toggle. |
| `CHANGELOG.md` | data (docs) | One GUI line under `<!-- cosmyx-slot: T11f -->`, flagged **Removed:** (way back to light). It says "Pull request: pending"; update to PR #98 when rebasing if it is still wrong. |

## Rebase risk zones

| Upstream file / function | In v2.5.1 | DEV vs v2.5.1 | Churn 2026 |
|--------------------------|-----------|---------------|-----------|
| `src/libslic3r/AppConfig.cpp`, `AppConfig::set_defaults()` | Anchor present: `show_center_of_mass` default block, then `#ifdef _WIN32` with `if (get("dark_color_mode").empty()) set("dark_color_mode", "0");` (line 438 on the tag vs 453 on DEV). Line 1 is `#include "Technologies.hpp"`. | 2 insertions, 38 deletions elsewhere in the file. | 81 |
| `src/slic3r/GUI/GUI_App.cpp`, `GUI_App::dark_mode()` | Present at line 4531 on the tag, identical head (`#ifdef SUPPORT_DARK_MODE`, `#if __APPLE__`, `CheckOSVersion(10, 14) && mac_dark_mode()`). | 22 insertions, 38 deletions elsewhere. | 246 |

Writers and readers of `dark_color_mode` (decision 0137 depends on this inventory) are the same set on the tag and on DEV: writes in `GUI_App.cpp` (`on_init_inner()` system-theme sync, macOS and Linux), `GUI_Utils.cpp` (`update_dark_config()`) and the Windows Preferences toggle; direct readers in `AboutDialog.cpp`, `GLCanvas3D.cpp`, `GLTexture.cpp`, `GUI_App.cpp`, `GUI_Utils.cpp`, `Plater.cpp` (two), `PrivacyUpdateDialog.cpp`, `TroubleshootDialog.cpp`. Verified with `git grep -n dark_color_mode upstream/v2.5.1 -- src` and on DEV: no site exists on DEV that is absent from the tag.

The wxWidgets fork: `SetAppearance` is a wxWidgets 3.3 API; if the deps on a release branch use another wx, `ColorMode.cpp` fails to compile on macOS/Linux.

## Intent to preserve

- `GUI_App::dark_mode()` is true on every OS and every system appearance, and the `dark_color_mode` key is `"1"` after every load, reset and `dark_mode()` call, so no upstream direct reader ever sees `"0"`.
- Native widgets on macOS and GTK are dark too (one `SetAppearance` call, main thread, once).
- The Windows toggle may stay visible but has no lasting effect; no hook in `Preferences.cpp`.

If upstream rewrote the hooked code: if `dark_mode()` moves or is renamed, hook the new central query with the same early return. If upstream adds a new writer of `dark_color_mode` that does not call `dark_mode()` afterwards, either call `Cosmyx::force_dark_mode()` at the end of that writer (one extra hook) or add a hook in the key's setter path. If `AppConfig::set_defaults()` is restructured, keep the call after every default and outside Windows-only blocks. If upstream itself adds a theme or appearance system with an explicit setting, prefer pinning that setting to dark instead of the early return.

## Verification

Catch2, `tests/cosmyx/test_color_mode.cpp`, tags `[cosmyx][ColorMode]`: "A fresh app config is dark on every OS", "The pinned value is the dark one", "Any other dark_color_mode value is forced back to dark", "Forcing an already dark config changes nothing", "Setting the defaults turns a light config dark", "A saved light config loads dark". Run `ctest --test-dir build -C Release -R cosmyx --output-on-failure`. `just test-scripts` and `just decisions` for the foundation checks.

The native appearance call is not unit tested (needs a running wxApp); the build on each OS must compile it. Manual: start the app on a machine with a light system theme (macOS and Linux) and on Windows with a config holding `dark_color_mode=0`; the UI is dark; on Windows, untick "Enable dark Mode", reopen Preferences, it shows ticked again. The GUI goldens branch captures the dark UI on three OSes.

## Known pitfalls

- Decision 0137: a future upstream write of `dark_color_mode` without a following `dark_mode()` call leaves direct readers light until the next call or restart; check new writes when merging upstream.
- Hook placement: line 3 of `GUI_App.cpp` is shared with the version include; a rebase conflict on the include block is likely if another branch also edits lines 2 to 4 (see Shared files).
- No CI breakages are recorded in this branch's own history (four commits, no fixups).

## Shared files with other branches

- `src/slic3r/GUI/GUI_App.cpp`: include block (line 2 version, line 3 this, line 4 goldens) and `dark_mode()` (goldens carries the same hook). `feat/cosmyx-install-paths` avoids this block on purpose.
- `src/libslic3r/AppConfig.cpp`: also hooked by `feat/cosmyx-stealth-mode` (one line, first statement of
  `get_stealth_mode()`) and `feat/cosmyx-cloud-server` (rewrites that line, adds an include after `#include "AppConfig.hpp"`).
  Integration total: 4 `Cosmyx` lines (dark 2, cloud 2). The three branches touch different lines, so they merge without
  conflict in the `branches.md` order.
- `test/cosmyx-gui-goldens` duplicates the four commits and `tests/cosmyx/test_color_mode.cpp`, and decisions 0136 to 0139 (byte-identical); merge dark-default first, then rebase goldens, which drops the duplicates.
- `CHANGELOG.md` (slot T11f; goldens' diff also contains this line, then adds T16), `wiki/decisions` numbers 0136 to 0139 (reserved range for T11 sub-tasks, see decision 0003).
