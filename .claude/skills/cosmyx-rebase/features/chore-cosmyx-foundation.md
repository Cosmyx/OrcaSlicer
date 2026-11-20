# chore/cosmyx-foundation (PR #86)

## Purpose

The base every other Cosmyx feature branch builds on. It gives Cosmyx code a home that upstream never edits, and reaches that home through a handful of one-line hooks, so merging upstream into `DEV` never conflicts. It delivers:

- `src/libslic3r/Cosmyx/` and `src/slic3r/GUI/Cosmyx/` (plus `GUI/Cosmyx/logic/` for wxWidgets-free GUI logic), each pulled into its CMake target by a glob (`Cosmyx.cmake`), so a feature only adds files.
- One seam, `Cosmyx::extend_print_config_def()`, where Cosmyx print options are added to `PrintConfigDef`. It ships three empty per-feature extenders (bed-temperature-off, CHT nozzle, ironing temperature) and an `add_option()` helper (because `ConfigDef::add()` is protected) that hands out serialization ordinals from a range starting at `1 << 30`, so they never collide with upstream ordinals.
- `GCodeHooks.hpp`, the single header `GCode.cpp` includes; features expose their G-code helpers through it.
- The `cosmyx_tests` Catch2 suite (`tests/cosmyx/`), globbed, every case tagged `[cosmyx]`.
- The repository rules in file form: `CHANGELOG.md` with per-task slot markers, the decision register `wiki/decisions/` (0001-0005), the `justfile`, `scripts/cosmyx/run_script_tests.py` (Python unittest plus Pester when PowerShell exists), `scripts/cosmyx/decisions.py`, and the `cosmyx-checks` workflow (script tests on Linux, macOS, Windows).
- Two flatpak fixes so `cosmyx_tests` is built and can read its data in the flatpak test leg.

## Parent and dependencies

Parent: `DEV`. It depends on no other Cosmyx branch; every other branch depends on it (the shared commits 6cbd27d0fc to 39c40f609f appear at the bottom of every child branch's history).

Upstream APIs used: `PrintConfigDef` (class, constructor, `options`, `by_serialization_key_ordinal`), `ConfigDef`/`ConfigOptionDef`, `PrintConfigDef::init_extruder_option_keys()`, `assign_printer_technology_to_unknown(..., ptFFF)`, the CMake targets `libslic3r`, `libslic3r_gui`, `libslic3r_tests`, the test helpers `tests/fff_print/test_helpers.cpp`, `test_common`, and the CMake functions `orcaslicer_discover_tests`, `orcaslicer_copy_test_dlls`, `add_precompiled_header`.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `src/libslic3r/CMakeLists.txt` | upstream hook | `include(Cosmyx/Cosmyx.cmake) # Cosmyx`, placed right after `source_group(TREE ${CMAKE_CURRENT_SOURCE_DIR} FILES ${lisbslic3r_sources})` and before `if (SLIC3R_STATIC)`. |
| `src/slic3r/CMakeLists.txt` | upstream hook | `include(GUI/Cosmyx/Cosmyx.cmake) # Cosmyx`, placed right after `source_group(TREE ${CMAKE_CURRENT_SOURCE_DIR} FILES ${SLIC3R_GUI_SOURCES})` and before `encoding_check(libslic3r_gui)` and the PCH setup. |
| `tests/CMakeLists.txt` | upstream hook | `add_subdirectory(cosmyx) # Cosmyx`, between `add_subdirectory(slic3rutils)` and `add_subdirectory(fff_print)`. |
| `src/libslic3r/PrintConfig.cpp` | upstream hook (2 lines) | Line 2: `#include "Cosmyx/ConfigDefExtensions.hpp" // Cosmyx` (right after `#include "PrintConfig.hpp"`). In `PrintConfigDef::PrintConfigDef()`: `Cosmyx::extend_print_config_def(*this); // Cosmyx`, between `this->init_extruder_option_keys();` and `assign_printer_technology_to_unknown(this->options, ptFFF);` so Cosmyx options become FFF options. |
| `src/libslic3r/GCode.cpp` | upstream hook | Line 2: `#include "Cosmyx/GCodeHooks.hpp" // Cosmyx`, right after `#include "ArcFitter.hpp"`. |
| `.github/workflows/build_flatpak.yml` | upstream hook | In the "Package flatpak test asset" step, the `find "$d/resources" -mindepth 1 -maxdepth 1 ! -name profiles ! -name printers ! -name images -exec rm -rf {} +` line gets `! -name cosmyx ! -name info` appended, preceded by the comment `# Cosmyx: cosmyx_tests also reads resources/cosmyx and resources/info.` (decision 0005). |
| `src/libslic3r/Cosmyx/Cosmyx.cmake`, `src/slic3r/GUI/Cosmyx/Cosmyx.cmake` | Cosmyx-owned | `file(GLOB ... CONFIGURE_DEPENDS)` of `*.cpp *.hpp` (GUI: also `logic/`, and `*.mm` on Apple with `SKIP_PRECOMPILE_HEADERS`), `target_sources(... PRIVATE ...)`, `source_group`. |
| `src/libslic3r/Cosmyx/ConfigDefExtensions.{hpp,cpp}` | Cosmyx-owned | `add_option`, `is_cosmyx_option`, `extend_print_config_def`, `extend_print_config_def_calls`, `option_ordinal_base`; throws `std::logic_error` on a key clash with an upstream option. |
| `src/libslic3r/Cosmyx/{BedTemperatureOff,IroningTemperature}.{hpp,cpp}`, `ChtNozzle.cpp`, `GCodeHooks.hpp` | Cosmyx-owned | Empty extenders, one file per feature, which feature branches fill in. |
| `src/slic3r/GUI/Cosmyx/Cosmyx.hpp`, `logic/.gitkeep` | Cosmyx-owned | Module placeholder. |
| `tests/cosmyx/CMakeLists.txt`, `cosmyx_tests.cpp`, `test_cosmyx_foundation.cpp` | test | Globs `test_*.cpp` and `GUI/Cosmyx/logic/*.cpp`; links `test_common libslic3r Catch2::Catch2WithMain`; `add_dependencies(libslic3r_tests cosmyx_tests)` so the flatpak leg (explicit upstream target list) builds it (commit 41b887876e). |
| `justfile`, `scripts/cosmyx/run_script_tests.py`, `scripts/cosmyx/decisions.py` | Cosmyx-owned (CI tooling) | Recipes `test-scripts`, `build-all`, `build-status`, `decisions`; optional `import?` lines for `scripts/cosmyx/just/{branding,goldens,i18n,macos-signing,signing,sync,tests,version}.just`. |
| `scripts/cosmyx/tests/test_foundation.py` | test | Pins justfile imports, changelog slots, decision slots, checks-workflow paths, the flatpak hooks, the register format, the runner. |
| `.github/workflows/cosmyx-checks.yml` | CI | Script tests on ubuntu/macos/windows for PRs and pushes to `DEV`, with a wide `paths:` list including the hooked upstream workflows `build_orca.yml` and `build_flatpak.yml`. |
| `CHANGELOG.md`, `wiki/decisions/0001-0005`, `wiki/decisions/README.md` | data/docs | Changelog with `<!-- cosmyx-slot: Tn -->` markers; decisions on layout, hook placement, slots, test layout, flatpak asset. |

## Rebase risk zones

| Upstream file | v2.5.1 vs DEV | Churn (commits since 2026-01-01 on DEV) |
|---|---|---|
| `src/libslic3r/PrintConfig.cpp` | Large diff (30 added, 307 removed lines in many hunks), but the hook anchors exist unchanged: line 2 `#include "PrintConfig.hpp"` and, near line 1003, `this->init_extruder_option_keys();` followed by `assign_printer_technology_to_unknown(this->options, ptFFF);`. | 20 |
| `src/libslic3r/GCode.cpp` | 147 added / 269 removed lines; first lines `#include "ArcFitter.hpp"` then `#include <tuple>` are identical, so the include hook still places cleanly. | 20 |
| `src/libslic3r/CMakeLists.txt` | Diffs elsewhere (OpenCASCADE, sources); the anchor `source_group(TREE ... ${lisbslic3r_sources})` followed by `if (SLIC3R_STATIC)` is intact. | 20 |
| `src/slic3r/CMakeLists.txt` | 1 added / 11 removed lines; anchor `source_group(TREE ... ${SLIC3R_GUI_SOURCES})` and `encoding_check(libslic3r_gui)` intact in the tag. | 20 |
| `tests/CMakeLists.txt` | Small diff (3 added / 5 removed). `add_subdirectory(libslic3r)`, `slic3rutils`, `fff_print` all present; the tag has an extra `add_subdirectory(cli)` block. | 9 |
| `.github/workflows/build_flatpak.yml` | DOES NOT EXIST in v2.5.1 (added to DEV later by a4de8cb891 "Build the Flatpak ... on Request"). In v2.5.1 the same `find "$d/resources" ... ! -name images -exec rm -rf {} +` line lives in `.github/workflows/build_all.yml` (line ~489, the flatpak test asset packaging). `unit_tests_flatpak.yml` in the tag only consumes the tar. | 1 |

## Intent to preserve

- Cosmyx code is reached only through single-line `// Cosmyx` / `# Cosmyx` hooks at stable places; `git grep Cosmyx` lists them all. Never widen a hook, never edit another upstream line.
- Cosmyx print options must be FFF options (defined before the `ptFFF` tagging) and must never shift upstream serialization ordinals.
- `cosmyx_tests` must be built and run in every test leg, flatpak included, and the flatpak test asset must keep `resources/cosmyx` and `resources/info`.
- Rebase onto v2.5.1: re-apply the five CMake/C++ hooks at the same anchors (they apply cleanly). For the flatpak asset hook, do not recreate `build_flatpak.yml`; add the two `! -name cosmyx ! -name info` terms and the `# Cosmyx` comment to the `find "$d/resources"` line in `.github/workflows/build_all.yml` of the tag, and update the `FlatpakTestAssetTests` / `FlatpakTestTargetTests` unit tests, which read `build_flatpak.yml`, to point at the file that holds the line. The flatpak test-target list lives in `scripts/flatpak/com.orcaslicer.OrcaSlicer.yml` (`libslic3r_tests fff_print_tests ... filament_group_tests`); `libslic3r_tests` must still exist there.

## Verification

- Catch2 (`ctest -R cosmyx` or `cosmyx_tests "[cosmyx]"`): "PrintConfigDef runs the Cosmyx dispatcher", "Every Cosmyx extender can run on a definition", "add_option registers a Cosmyx option", "Upstream options keep their upstream ordinals", "Every Cosmyx option default is within its own range".
- `just test-scripts` (`scripts/cosmyx/tests/test_foundation.py`: `JustfileTests`, `ChangelogTests`, `DecisionSlotTests`, `ChecksWorkflowTests`, `FlatpakTestTargetTests`, `FlatpakTestAssetTests`, `DecisionTests`, `RunnerTests`), `just decisions`.
- `git merge-tree` with the new base: zero conflicts. `git grep -n "Cosmyx" -- src tests .github/workflows` shows exactly the hooks listed above.
- CI: `build_all` dispatched on the branch (unit tests job runs `cosmyx_tests` with the upstream suites, flatpak legs included); `cosmyx-checks` green on 3 OS.

## Known pitfalls

- 41b887876e: the flatpak leg builds an explicit list of upstream test targets, so `cosmyx_tests` was registered but not built (`cosmyx_tests_NOT_BUILT`). Fixed by hanging it on `libslic3r_tests` with `add_dependencies`.
- be423c6998: the flatpak asset step deleted `resources/cosmyx` and `resources/info`, so Cosmyx tests reading models and the nozzle hardness table failed in that leg only.
- 92830e0a8b: the checks workflow `paths:` must include `cosmyx-src/**`, `.github/workflows/cosmyx-*.yml` and the hooked build workflows, or wiring tests do not run when upstream edits them.
- 5fbe728f6f: justfile imports are optional (`import?`) so feature branches never edit the justfile.
- v2.5.1 pass (2026-11-20, copy tip `3f92fbf1f0`): `be423c6998` hit the expected modify/delete on `build_flatpak.yml`. Resolved by `git rm`, the hook on the `find "$d/resources"` line of `build_all.yml` (line 489-490 on the tag), `FlatpakTestAssetTests` reading `build_all.yml`, and decision 0005 naming both files. `build_all.yml` is committed with CRLF upstream: edit it as bytes and keep CRLF (a Python `read_text`/`write_text` round trip rewrites the whole file). `ChecksWorkflowTests` still passes with `build_flatpak.yml` in `paths:`; `libslic3r_tests` is still in the flatpak target list (manifest line 412).

## Shared files with other branches

Every child branch contains these foundation files (identical copies, so they merge cleanly only while untouched): `justfile`, `CHANGELOG.md`, `scripts/cosmyx/run_script_tests.py`, `scripts/cosmyx/decisions.py`, `scripts/cosmyx/tests/test_foundation.py` (the child branches carry slightly different versions, 190 to 198 lines vs 230 here, because the later foundation commits 41b887876e and be423c6998 are not in them), `.github/workflows/cosmyx-checks.yml`, `wiki/decisions/0001-0005` and `README.md`, the whole `src/libslic3r/Cosmyx/` skeleton, `src/slic3r/GUI/Cosmyx/`, `tests/cosmyx/`, and the three upstream hooks in `CMakeLists.txt`/`PrintConfig.cpp`/`GCode.cpp`. Feature branches also later edit the empty extender files (`BedTemperatureOff.cpp`, `ChtNozzle.cpp`, `IroningTemperature.cpp`) and `CHANGELOG.md` slots. Rebase this branch first, then rebase children on it.
