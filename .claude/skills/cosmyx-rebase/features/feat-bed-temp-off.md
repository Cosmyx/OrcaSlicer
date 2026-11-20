# feat/bed-temp-off (PR #88)

## Purpose

A Cosmyx printer needs filament profiles that print with the bed heater off. Upstream bed temperature options (every `*_plate_temp` and `*_plate_temp_initial_layer` option) accept 0 and up, and 0 already means "this filament does not support this plate" (`Print::validate()` refuses the print). This feature makes -1 mean "bed heater off":

- every per-plate bed temperature option accepts a minimum of -1 (matched by key pattern, so a plate type added upstream is covered too);
- `GCodeWriter::set_bed_temperature()` turns -1 into `M140 S0`, written once, and never waits (no `M190`);
- the derived start/custom G-code placeholders `bed_temperature`, `bed_temperature_initial_layer`, `bed_temperature_initial_layer_single` and `first_layer_bed_temperature` are clamped to 0, so a template such as `M190 S[bed_temperature_initial_layer_single]` never writes `S-1`.

0 keeps its upstream meaning. Raw plate keys (`[hot_plate_temp]`) and the `; first_layer_bed_temperature` header comment keep -1 on purpose (decision 0012). Upstream tooltips are left untouched (decision 0011). Decisions: 0010, 0011, 0012. Changelog slot: T1 (libslic3r).

## Parent and dependencies

- Parent: `DEV`. The PR body says "Depends on #86": the branch carries the foundation commits `6cbd27d0fc`..`39c40f609f` (Cosmyx module folders, `ConfigDefExtensions`, `cosmyx_tests` suite, changelog, decision register, justfile, `cosmyx-checks` workflow) because PR #86 (`chore/cosmyx-foundation`) is not merged in DEV yet. Its own commits are `87e5e9c458` (feature), `77e637803d` (tests), `c99af113e5` (docs), `de8058dc33` (test fixture fix).
- No dependency on the other four feature branches. They all share the foundation stubs.
- Upstream APIs used: `PrintConfigDef::options`, `ConfigOptionDef::min`, `coInts`; `PlaceholderParser::config_writable()`, `DynamicConfig::option<ConfigOptionInts>()`; `GCodeWriter::set_bed_temperature()` members `m_last_bed_temperature` and `m_last_bed_temperature_reached`; `GCode::_do_export()` placeholder `first_layer_bed_temperature`; `Print::validate()` (tests only).

## Changes

| File | Kind | What it does |
|---|---|---|
| `src/libslic3r/Cosmyx/BedTemperatureOff.hpp` | Cosmyx-owned | Declares `bed_temperature_off = -1`, `is_bed_temperature_key()`, `clamp_bed_temperature_placeholders()`. |
| `src/libslic3r/Cosmyx/BedTemperatureOff.cpp` | Cosmyx-owned | `extend_bed_temperature_off(def)`: for every `coInts` option whose key ends with `_plate_temp` or `_plate_temp_initial_layer`, sets `min = -1`. `clamp_bed_temperature_placeholders()`: `max(value, 0)` on the four placeholders when set. |
| `src/libslic3r/Cosmyx/GCodeHooks.hpp` | Cosmyx-owned (foundation) | Includes `BedTemperatureOff.hpp` so GCode.cpp needs one include only. |
| `src/libslic3r/GCode.cpp` | upstream hook | Line 2 (after `#include "ArcFitter.hpp"`): `#include "Cosmyx/GCodeHooks.hpp" // Cosmyx`. In `GCode::_do_export()`, right after `this->placeholder_parser().set("first_layer_bed_temperature", new ConfigOptionInts(*first_bed_temp_opt));` (below the comment `SoftFever: support variables first_layer_temperature and first_layer_bed_temperature`): `Cosmyx::clamp_bed_temperature_placeholders(this->placeholder_parser()); // Cosmyx` |
| `src/libslic3r/GCodeWriter.cpp` | upstream hook | First statement of `std::string GCodeWriter::set_bed_temperature(int temperature, bool wait)`: `if (temperature < 0) { if (m_last_bed_temperature_reached) m_last_bed_temperature = -1; temperature = 0; wait = false; } // Cosmyx: -1 = bed off, M140 S0 once, never wait (decision 0010)` |
| `src/libslic3r/PrintConfig.cpp` | upstream hook (foundation) | Line 2: `#include "Cosmyx/ConfigDefExtensions.hpp" // Cosmyx`. In `PrintConfigDef::PrintConfigDef()` between `this->init_extruder_option_keys();` and `assign_printer_technology_to_unknown(this->options, ptFFF);`: `Cosmyx::extend_print_config_def(*this); // Cosmyx` |
| `src/libslic3r/CMakeLists.txt` | upstream hook (foundation) | After `source_group(TREE ${CMAKE_CURRENT_SOURCE_DIR} FILES ${lisbslic3r_sources})`: `include(Cosmyx/Cosmyx.cmake) # Cosmyx` |
| `src/slic3r/CMakeLists.txt` | upstream hook (foundation) | After `source_group(TREE ${CMAKE_CURRENT_SOURCE_DIR} FILES ${SLIC3R_GUI_SOURCES})`, before `encoding_check(libslic3r_gui)`: `include(GUI/Cosmyx/Cosmyx.cmake) # Cosmyx` |
| `tests/CMakeLists.txt` | upstream hook (foundation) | Between `add_subdirectory(slic3rutils)` and `add_subdirectory(fff_print)`: `add_subdirectory(cosmyx) # Cosmyx` |
| `src/libslic3r/Cosmyx/{ConfigDefExtensions.*,Cosmyx.cmake,ChtNozzle.cpp,IroningTemperature.*}`, `src/slic3r/GUI/Cosmyx/*` | Cosmyx-owned (foundation) | Dispatcher `extend_print_config_def()` and empty extender stubs for the other features. |
| `tests/cosmyx/test_bed_temperature_off.cpp` | test | 8 Catch2 cases, tag `[cosmyx][BedTemperatureOff]` (see Verification). |
| `tests/cosmyx/{CMakeLists.txt,cosmyx_tests.cpp,test_cosmyx_foundation.cpp}` | test (foundation) | Suite wiring, foundation checks. |
| `wiki/decisions/0010..0012` | docs | Decisions of this feature. `0001..0004` and `README.md` are foundation. |
| `CHANGELOG.md`, `justfile`, `scripts/cosmyx/*`, `.github/workflows/cosmyx-checks.yml` | CI / docs (foundation) | Shared tooling. Feature line under `<!-- cosmyx-slot: T1 -->`. |

## Rebase risk zones

Checked against `upstream/v2.5.1` (tag eef7710cb1). The hook patch of this branch (all upstream files, 3-way, `git apply --check` on the v2.5.1 tree) applies cleanly.

| Upstream file | Differs DEV vs v2.5.1 | Commits since 2026-01-01 on DEV | Notes |
|---|---|---|---|
| `src/libslic3r/GCodeWriter.cpp` | No diff at all | 79 | `set_bed_temperature` identical; lowest risk. |
| `src/libslic3r/GCode.cpp` | Large (DEV has +269/-147 lines vs tag), anchors still present: `first_layer_bed_temperature` placeholder at line 4049 in the tag (4056 in DEV); first include `ArcFitter.hpp` | 342 | Highest churn file; only context lines move. |
| `src/libslic3r/PrintConfig.cpp` | Large, anchor `init_extruder_option_keys();` present (line 1003 in the tag) | 385 | Include on line 2 and ctor call are shared with every feature. |
| `src/libslic3r/CMakeLists.txt`, `src/slic3r/CMakeLists.txt`, `tests/CMakeLists.txt` | Small differences nearby (tests/CMakeLists differs in `CATCH_EXTRA_ARGS` and `orcaslicer_discover_tests`, DEV has `--warn NoAssertions`) | 127 / 205 / 9 | `orcaslicer_discover_tests` and `orcaslicer_copy_test_dlls` still exist in the tag, so `tests/cosmyx/CMakeLists.txt` works. |

APIs checked present in the tag: `ConfigOptionDef::min`, `GCodeWriter::m_last_bed_temperature_reached`, `PlaceholderParser::config_writable`, `Print::validate` bed type error. All present.

## Intent to preserve

- With any `*_plate_temp(_initial_layer)` = -1: G-code contains `M140 S0` (once, even on a fresh writer whose state assumes bed 0, because the bed may be hot from a previous print), never `M190` for it, never `S-1`.
- -1 passes config validation (`min = -1`), -2 is refused.
- 0 still produces the unsupported-plate error from `Print::validate()`.
- A positive temperature behaves exactly as upstream.
- If upstream rewrites `set_bed_temperature`, re-implement at its entry: map any negative request to "temperature 0, no wait, emit one `M140 S0` even if the writer thinks the bed is at 0". If upstream changes how the placeholders are set in `_do_export`, re-hook after the last place the four bed placeholders are written, not at a fixed line. If a new plate option has a different key suffix, extend `is_bed_temperature_key()` instead of listing keys.

## Verification

- Catch2 (suite `cosmyx_tests`, tag `[cosmyx][BedTemperatureOff]`), in `tests/cosmyx/test_bed_temperature_off.cpp`: "Bed temperature keys are recognised by pattern", "Every plate bed temperature accepts -1", "Config validation accepts -1 and refuses -2 as a bed temperature", "The G-code writer turns the bed off for -1 and never waits", "A print with the bed off never writes a negative or waited bed temperature", "Bed temperature placeholders read 0 when the bed is off", "Bed temperature placeholders keep positive values", "A bed temperature of 0 still means the filament does not support the plate".
- Foundation: `test_cosmyx_foundation.cpp` (5 cases, tag `[cosmyx]`), `just test-scripts` (Python tests of `scripts/cosmyx`), workflow `cosmyx-checks`.
- Run: `ctest --test-dir build -C Release -R cosmyx` (build is CI only here: dispatch `build_all.yml` on the branch).
- Manual: slice a print with `hot_plate_temp_initial_layer = -1` and a start G-code `M190 S[bed_temperature_initial_layer_single]`; the output has `M140 S0`, no `S-1`.

## Known pitfalls

- `de8058dc33`: `Print::validate()` returns its first error. With Marlin flavour and relative E distances, an empty `layer_change_gcode` stops at the "G92 E0" reset check before the bed type check, so the "bed 0 unsupported" assertion passed for the wrong reason. The test fixture sets `layer_change_gcode` to `G92 E0`; keep that when the test is re-applied.
- Do not edit the twelve upstream tooltip strings to mention -1 (decision 0011): it would conflict and change every translation.
- Use `-1` only through the writer: `m_last_bed_temperature` is set to -1 only when the bed had been reached, to force one `M140 S0`.

## Shared files with other branches

- All five branches carry the same foundation commits and the same stubs in `src/libslic3r/Cosmyx/` (`BedTemperatureOff.*`, `ChtNozzle.cpp`, `IroningTemperature.*`, `ConfigDefExtensions.*`, `GCodeHooks.hpp`). This branch owns the real `BedTemperatureOff.*`; the others hold stubs of it. `GCodeHooks.hpp` lists the headers GCode.cpp sees (bed and ironing only; the fan fix is included directly by CoolingBuffer.cpp).
- `GCode.cpp` line 2 include is identical in all branches (same line, no conflict if identical). `PrintConfig.cpp` line 2 and the `extend_print_config_def` call are identical in all branches.
- `CHANGELOG.md`: slot T1 only; other branches edit their own slot (T2 CHT, T3 ironing, T4 fan, T5 models), so rebases are conflict free if slots are kept.
- `wiki/decisions/README.md` and decision numbers: range 0010-0019 for this branch.
- `tests/cosmyx/CMakeLists.txt` globs `test_*.cpp`: no edit needed to add tests.
