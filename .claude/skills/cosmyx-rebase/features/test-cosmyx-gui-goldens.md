# test/cosmyx-gui-goldens (PR #107)

Analysed commits: `origin/feat/cosmyx-version..origin/test/cosmyx-gui-goldens` (12 commits: 4 are copies of the dark-mode feature, 8 are goldens). Compared with `origin/DEV` and `upstream/v2.5.1`.

## Purpose

Every screen of the built application is pinned to a committed image, on Linux, macOS and Windows, so an unintended pixel change is caught (shared rule "GUI goldens"; task T16). After each "Build all" run a workflow starts the produced app on a runner of each OS, walks it through every main tab, menu, Preferences tab, settings page, catalog command and calibration dialog, then drives a slice from the UI. It captures each surface and compares it with `tests/cosmyx/gui/goldens/<os>/`, and posts the commit status `cosmyx/gui-goldens`.

Design (decisions 0162 to 0179, `wiki/cosmyx/gui-goldens.md`):

- An in-app driver (`GoldenDriver`) runs a JSON script from a 50 ms timer, opening surfaces through the application's own entry points, never synthetic clicks. It starts only when the environment variable `COSMYX_GUI_DRIVER_DIR` names a folder (decision 0163), so normal use costs one `getenv`.
- An external Python harness (`scripts/cosmyx/gui_goldens`) seeds a clean data folder, starts the build, captures the screen with one native backend per OS (decision 0165, a recorded exception to the "always Docker" rule), and compares. Protocol is files only (`events.jsonl`, `ack-<seq>`).
- Linux: byte-exact in a pinned Docker image (Ubuntu by digest, apt snapshot, Mesa llvmpipe, Xvfb, openbox). Windows and macOS: pixel tolerance from `tolerance.json`, WebViews masked. The first golden set is not committed: the three `goldens/<os>/` folders hold `.gitkeep`; CI generates them (update mode, `just goldens-gui RUN_ID update`, then `goldens-gui-fetch`).
- It also needs dark mode (all captures are dark), hence the copied dark-mode commits.

## Parent and dependencies

- Parent: `feat/cosmyx-version` (PR #93). The driver includes `logic/CosmyxVersion.hpp` and sends `display_version()` in its `hello` event.
- Contains copies of `feat/cosmyx-dark-default` (PR #98) commits: libslic3r `ColorModeDefault`, GUI `ColorMode`, their hooks (`AppConfig.cpp`, `GUI_App.cpp` `dark_mode()`), `tests/cosmyx/test_color_mode.cpp`, decisions 0136 to 0139. These are byte-identical to PR #98 content.
- Depends on the foundation (T0, PR #86).
- Soft dependency on task T13 (test CI, not in this branch): `cli.py` imports `artifact_checks` at runtime (`slice` rules for the UI slice G-code, `mesa_win` for the pinned Mesa on Windows, `inventory`). Without that package the slice check reports "artifact_checks.slice (T13) is not available" and the Windows Mesa step cannot run. Check T13 is present before expecting a green goldens run.
- Depends on the "Build all" workflow (`name: Build all`, file `build_all.yml`) and its artifact names (picked by `cli.py` `pick_artifacts`: Linux AppImage, macOS DMG/app, Windows x64 portable not MSVC).
- Upstream classes and functions used by `GoldenDriver.cpp`: `GUI_App` (`mainframe`, `plater()`, `tabs_list`, `params_dialog()`, `open_preferences(tab)`, `is_closing()`), `MainFrame` (`select_tab`, `GetMenuBar`), `Tab::activate_option`, `Plater::load_files(..., LoadStrategy::LoadModel)` (`libslic3r/Format/ProjectStrategy.hpp`), `NativeCommands::catalog()` and `NativeCommands::run(key, param)`, `BBLTopbar`, `DailyTips`, `NotificationManager`, `OpenGLManager`, `ParamsDialog`/`ParamsPanel`, `PartPlate`, `Preferences`, `GLCanvas3D`, `Preset`, `libslic3r/Utils.hpp`, wx `auibar`, `menu`, `timer`, `webview`, `glcanvas`.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `src/slic3r/GUI/GUI_App.cpp` | upstream hook | Line 4 (after `Cosmyx/ColorMode.hpp`): `#include "Cosmyx/GoldenDriver.hpp" // Cosmyx`. In `GUI_App::on_init_inner()`, idle handler: `Cosmyx::start_golden_driver_if_requested(); // Cosmyx` directly after `this->post_init();` and before `update_publish_status();`. Plus the dark-mode hooks `#include "Cosmyx/ColorMode.hpp" // Cosmyx` and `if (Cosmyx::force_dark_mode()) return true; // Cosmyx` in `GUI_App::dark_mode()` (shared with PR #98). A wiring test asserts exactly two goldens hook lines. |
| `src/libslic3r/AppConfig.cpp` | upstream hook | Same two dark-mode hook lines as PR #98 (include on line 2; `Cosmyx::force_dark_color_mode(*this); // Cosmyx` before the `#ifdef _WIN32` block of `AppConfig::set_defaults()`). |
| `src/slic3r/GUI/Cosmyx/GoldenDriver.hpp`, `.cpp` | Cosmyx-owned | Driver; `start_golden_driver_if_requested()` is a static-once no-op unless `COSMYX_GUI_DRIVER_DIR` is set; never deleted (destroying its timer after wx shutdown would crash on exit). No per-OS `#if` in this file (a test enforces it). |
| `src/slic3r/GUI/Cosmyx/logic/GoldenScript.hpp`, `.cpp` | Cosmyx-owned (wx-free) | Script parser, generators, `menu_items` classification of every `NativeCommands::catalog()` key, surface ids, `surfaces.txt`, menu tree text, protocol events. Compiled by `cosmyx_tests`. |
| `src/libslic3r/Cosmyx/ColorModeDefault.*`, `src/slic3r/GUI/Cosmyx/ColorMode.*` | Cosmyx-owned | See PR #98. |
| `tests/cosmyx/test_golden_script.cpp`, `test_color_mode.cpp` | test | Catch2. |
| `tests/cosmyx/gui/script.json` | data | The script: sections 00 start, 10 main tabs, 20 menus, 30 catalog dialogs, 40 Preferences tabs, 50 loaded cube and settings pages, 60 calibrations, 70 selection and context menu, 90 UI slice, 99 skipped commands; `menu_items` rules; `exclude` list. |
| `tests/cosmyx/gui/tolerance.json` | data | Per-OS comparison: linux exact; macos and windows `channel_delta` 8, `max_diff_ratio` 0.0005, tile 16, `max_tile_ratio` 0.10, WebView mask. |
| `tests/cosmyx/gui/fixtures/OrcaSlicer.conf.in` | data | Seeded app config template. |
| `tests/cosmyx/gui/docker/Dockerfile` | CI/data | Pinned Linux image. |
| `tests/cosmyx/gui/goldens/{linux,macos,windows}/.gitkeep`, `.gitattributes` | data | Empty golden folders; `*.png binary`, `*.txt text eol=lf`. |
| `scripts/cosmyx/gui_goldens/*.py` | Cosmyx-owned (script) | `cli.py` (resolve, run, compare, fetch, review, local), `capture*.py`, `input_*.py`, `launch.py`, `compare.py`, `masks.py`, `png.py` (strict decoder), `protocol.py`, `report.py`, `seed.py`. |
| `scripts/cosmyx/just/goldens.just` | Cosmyx-owned (recipes) | `goldens-gui`, `goldens-gui-stability`, `goldens-gui-fetch`, `goldens-gui-review`, `goldens-gui-local`, `goldens-gui-status`. |
| `scripts/cosmyx/tests/test_gui_goldens_*.py`, `test_breaker_{golden_protocol_shapes,golden_surface_ids,png_crc,png_decoder}.py` | test | unittest. |
| `.github/workflows/cosmyx-gui-goldens.yml` | CI | Triggers: `workflow_run` of "Build all" (completed), `workflow_dispatch` (run_id, mode compare/update, stability), weekly schedule `23 4 * * 1`. Jobs: resolve, capture (matrix linux/macos-15/windows-2025), status. Skips when `github.repository == 'OrcaSlicer/OrcaSlicer'`. |
| `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md` | test / docs | Add slot T16 to the GUI area list. |
| `CHANGELOG.md` | docs | The dark-mode line (T11f) and a T16 line under `<!-- cosmyx-slot: T16 -->` (GUI area). Both say "Pull request: pending". |
| `wiki/cosmyx/gui-goldens.md`, `wiki/decisions/0162` to `0179` | docs | Architecture, hooks, protocol, per-OS capture, image, rendering, comparison, masks, clean runs, PNG, update flow, command classification, surfaces, stability, English only, status, deferred items, input validation. |

Foundation hooks (identical in every branch): `include(Cosmyx/Cosmyx.cmake) # Cosmyx` after `source_group(TREE ...)` in `src/libslic3r/CMakeLists.txt`; `include(GUI/Cosmyx/Cosmyx.cmake) # Cosmyx` in `src/slic3r/CMakeLists.txt`; `add_subdirectory(cosmyx) # Cosmyx` in `tests/CMakeLists.txt`; two lines in `PrintConfig.cpp`; one include in `GCode.cpp`. The version-feature hooks (five one-line edits plus the `build_orca.yml` step) are inherited from the parent branch, not owned here.

## Rebase risk zones

| Upstream file / function | v2.5.1 vs DEV | Churn 2026 |
|--------------------------|---------------|-----------|
| `src/slic3r/GUI/GUI_App.cpp`: `this->post_init();` in the `on_init_inner()` idle handler | Anchor present on the tag (line 3876, followed by blank line and `update_publish_status();`). File differs elsewhere: 22 insertions, 38 deletions. | 246 |
| `NativeCommands.cpp/.hpp` (the driver and `script.json` classify every catalog key) | No difference between DEV and the tag, so the classification holds on v2.5.1. A new upstream command fails `test_golden_script` and the script tests until it gets a `menu_items` rule. | 18 |
| `Preferences.cpp` (six tabs captured; settings pages) | 241 insertions, 415 deletions between DEV and the tag: the captured tabs may differ; the goldens (not committed yet) must be regenerated per base. | 99 |
| `MainFrame.cpp` (`select_tab`, menubar), `Tab.cpp` (`activate_option`), `Plater.cpp` (`load_files`) | Signatures used exist on both (`select_tab`, `activate_option`, `load_files`, `open_preferences`, `params_dialog()`, `tabs_list` each present on the tag and DEV). Diffs elsewhere: MainFrame 6/12, Tab 30/52, Plater 199/697 lines. | 187, 424, 562 |
| `AppConfig.cpp`, `dark_mode()` | See PR #98. | 81, 246 |
| `.github/workflows/build_all.yml` and `build_orca.yml` | The workflow listens to `workflows: ["Build all"]` (name identical on tag and DEV). `build_all.yml` differs by 261 insertions, 55 deletions. Artifact names on the tag: `OrcaSlicer_Linux_ubuntu_<ver>..._<ver>`, `OrcaSlicer_Windows_<ver>_portable`, `OrcaSlicer_Mac_universal_<ver>` (DEV additionally uploads `OrcaSlicer_Mac_<arch>_<ver>` at line 246 of `build_orca.yml`, absent on the tag); `pick_artifacts` must still find the Linux AppImage, macOS and Windows portable artifacts. Do not trust this on a release branch without running resolve against a real run. | 86 |

The goldens themselves are base-specific: pixels depend on the upstream UI. Rebasing onto v2.5.1 changes the UI (and the version label), so goldens generated on DEV are not valid on the tag; regenerate with update mode on the rebased branch.

## Intent to preserve

- Inert by default: the driver does nothing unless `COSMYX_GUI_DRIVER_DIR` is set; only two hook lines in `GUI_App.cpp`.
- Every surface (tab, menu, dialog, state) is listed in `script.json`; every `NativeCommands` key has a rule; the protocol is files only; Linux byte-exact in the pinned image; Windows and macOS within the recorded tolerance.
- Failed validation of events, ids and PNGs is a failed surface, never a crash or a write outside the images folder (decision 0179).
- Harness and image always come from the workflow's own commit; fork builds are never run; MIXED only reports.

If upstream rewrote the hooked code: if `post_init()` is renamed or moved, call `start_golden_driver_if_requested()` from the first point where the main frame, plater and 3D canvas exist and the app is idle. If `NativeCommands`, `Tab::activate_option`, `MainFrame::select_tab` or `Plater::load_files` change signature, adapt only `GoldenDriver.cpp` (the one place that calls them); do not add hooks. If menu construction changes (top bar vs menu bar), update the capture kinds in `script.json`, not upstream files. If "Build all" is renamed or its artifacts change, edit the `workflow_run` name and `pick_artifacts`.

## Verification

Catch2 (`cosmyx_tests`, tag `[cosmyx][GoldenScript]`): "Slugs are lower-case ASCII words joined by dashes", "Surface ids are two digits and a slug", "Capture kinds round-trip through their names", "A valid script parses with its defaults", "Script errors are all reported", "Every catalog key needs a rule and every rule a catalog key", "Generators expand to the surfaces the application reports", "macOS menus are menu bar captures", "Expansion reports unclassified commands, duplicates and bad ids", "surfaces.txt lists every step and every exclusion", "The menu tree text golden is stable and readable", "Protocol events are one JSON object each", "The shipped golden script is valid"; plus `[ColorMode]` cases from PR #98.

Script tests (`just test-scripts`): `test_gui_goldens_{capture,cli,compare,png,protocol,script,seed_launch,wiring}.py` and four `test_breaker_*` files. The wiring test pins: exactly two hook lines in `GUI_App.cpp`, no per-OS code in the driver, workflow triggers, status context `cosmyx/gui-goldens`, runner choices, untrusted values passed only through `env`, artifact layout, the six recipes (each with a comment), the Docker base pinned by digest and snapshot, and decisions 0162 to 0178 present. The macOS test checks Screen Recording with `CGPreflightScreenCaptureAccess` and skips with a reason otherwise.

Manual or CI: run `build_all` on the branch (`just build-all <branch>`), then `just goldens-gui <run id> update`, `just goldens-gui-fetch <goldens run id>`, `just goldens-gui-review`, look at every image, commit goldens, run `just goldens-gui-stability <run id>` (two passes must match), then a compare run must report success. `just goldens-gui-local <run id>` runs the Linux pass in Docker.

## Known pitfalls

- `6ee87da92f`: `MainFrame` has no public `menubar()` accessor; use `wxFrame::GetMenuBar`. Dispatching events to the 3D canvas needs the complete `wxGLCanvas` type (`#include <wx/glcanvas.h>`). The driver did not compile on CI until then.
- `8c3b40c84c` (breaker round): surface ids like `../x`, `CON`, `a:b` wrote outside the images folder or failed on Windows; repeated ids overwrote images; wrong-shaped events and damaged PNGs escaped as raw exceptions; PNG chunk CRCs were never checked. Fixed by strict id pattern, `protocol.validate`, strict PNG decoder (decision 0179). Never loosen.
- `e57b431160`: the Windows launcher reads `--sw-renderer` but also passes it to the command line parser, which rejects it ("Invalid option"). The harness now copies the pinned Mesa DLLs next to the executable and starts with `mesa_win.run_env()` (depends on T13's `artifact_checks.mesa_win`).
- The `import? 'scripts/cosmyx/just/goldens.just'` line is in the foundation tip's justfile (commit `92830e0a8b`), not in the older foundation copy this branch carries. After the rebase onto the full foundation the recipes are reachable through `just`; never add the import in this branch (the justfile is foundation-only).
- CRLF on Windows checkouts: read text fixtures EOL-agnostically (see the install-paths pitfall `7f51119c40`); goldens `.gitattributes` forces `*.txt text eol=lf`.
- Windows runner must be 1920x1080 at 96 DPI (the workflow throws otherwise); macOS needs Screen Recording permission.
- The workflow's changed-files check calls `compare/DEV...<sha>`; if DEV is renamed, adapt.
- v2.5.1 pass: adapted with `124e62829c`. The tag's `PreferencesTab` enum has 4 values (General, Control, Graphics, Online); DEV has 6. The driver casts the index of a tab name to `PreferencesTab`, so `preferences_tabs()` in `GoldenScript.cpp` must match the upstream enum exactly; the script test now compares the enum with that list. Restore the six names on a base that has them.
- v2.5.2 pass: v2.5.2 keeps the four-tab `PreferencesTab` enum; the same adaptation, committed as `da81bbfea6`.

## Shared files with other branches

- `GUI_App.cpp` include block (lines 2 to 4: version, ColorMode, GoldenDriver) and `dark_mode()`; `AppConfig.cpp` (dark mode).
- Duplicates PR #98: `ColorModeDefault.*`, `ColorMode.*`, `test_color_mode.cpp`, decisions 0136 to 0139, the T11f changelog line. Merge `feat/cosmyx-dark-default` first, then rebase this branch.
- `wiki/decisions/0003-changelog-slots.md` and `scripts/cosmyx/tests/test_foundation.py`: this branch adds slot T16 (any branch that edits the slot lists conflicts here).
- `CHANGELOG.md`: T11f and T16 lines. `wiki/decisions/`: 0162 to 0179 (T16 range).
- `.github/workflows/cosmyx-checks.yml` triggers include `.github/workflows/cosmyx-*.yml`, so the new workflow is covered by path filters.
- `justfile` imports (see pitfalls). `scripts/cosmyx/tests/` is shared with every script test.
