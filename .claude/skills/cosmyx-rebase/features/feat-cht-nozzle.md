# feat/cht-nozzle (PR #89)

## Purpose

Adds the CHT nozzle (hardness HRC 65) as a selectable `nozzle_type` in printer settings, next to the upstream types (tungsten carbide, HRC 85, is kept unchanged). A CHT nozzle can be saved in a printer profile and drives the abrasive-filament hardness check through `Print::get_hrc_by_nozzle_type()`. Device/BBL display maps are deliberately not touched (decision 0021, no firmware reports CHT). Decision 0022 proposes the same patch upstream; if upstream accepts it, the Cosmyx hooks become redundant (the extender is a no-op when "cht" is already present). Decisions: 0020, 0021, 0022. Changelog slot: T2 (libslic3r).

## Parent and dependencies

- Parent: `DEV`. Carries the foundation commits `6cbd27d0fc`..`39c40f609f` (PR #86, not yet in DEV). Own commits: `4f2610f257` (feature), `ecd0843a05` (docs), `08d8d62f96` (fix).
- No dependency on other feature branches.
- Upstream symbols used: `enum NozzleType` (`CommonDefs.hpp`, values `ntUndefine, ntHardenedSteel, ntStainlessSteel, ntTungstenCarbide, ntBrass, ntE3D, ntCount`), `s_keys_map_NozzleType`, `NozzleTypeEumnToStr`, `NozzleTypeStrToEumn`, config option `nozzle_type` (`coEnums`, `enum_values`/`enum_labels`), `resources/info/nozzle_info.json` (`nozzle_hrc`), `Print::get_hrc_by_nozzle_type()`, `Choice::get_value()` in `GUI/Field.cpp` (stores the combo position as the enum value).

## Changes

| File | Kind | What it does |
|---|---|---|
| `src/libslic3r/CommonDefs.hpp` | upstream hook | In `enum NozzleType`, between `ntBrass,` and `ntE3D,`: `ntCHT, // Cosmyx`. This makes `ntCHT = 5`, `ntE3D = 6`, `ntCount = 7`. |
| `src/libslic3r/PrintConfig.hpp` | upstream hook | In `NozzleTypeEumnToStr` after the `undefine` entry: `{NozzleType::ntCHT, "cht"}, // Cosmyx`. In `NozzleTypeStrToEumn` after the `undefine` entry: `{"cht", NozzleType::ntCHT}, // Cosmyx`. |
| `src/libslic3r/PrintConfig.cpp` | upstream hook | In `s_keys_map_NozzleType` after `{ "undefine", int(NozzleType::ntUndefine) },`: `{ "cht", int(NozzleType::ntCHT) }, // Cosmyx`. Plus foundation hooks: line 2 `#include "Cosmyx/ConfigDefExtensions.hpp" // Cosmyx`, and `Cosmyx::extend_print_config_def(*this); // Cosmyx` between `init_extruder_option_keys();` and the `ptFFF` tagging in `PrintConfigDef::PrintConfigDef()`. |
| `resources/info/nozzle_info.json` | data / upstream hook | First entry of `nozzle_hrc`: `"cht": 65,`. JSON has no comments so no marker; decision 0020 records it. |
| `src/libslic3r/GCode.cpp` | upstream hook (foundation) | Line 2: `#include "Cosmyx/GCodeHooks.hpp" // Cosmyx` (after `#include "ArcFitter.hpp"`). |
| `src/libslic3r/CMakeLists.txt`, `src/slic3r/CMakeLists.txt`, `tests/CMakeLists.txt` | upstream hook (foundation) | `include(Cosmyx/Cosmyx.cmake) # Cosmyx` after libslic3r `source_group`; `include(GUI/Cosmyx/Cosmyx.cmake) # Cosmyx` before `encoding_check(libslic3r_gui)`; `add_subdirectory(cosmyx) # Cosmyx` between `slic3rutils` and `fff_print`. |
| `src/libslic3r/Cosmyx/ChtNozzle.cpp` | Cosmyx-owned | `extend_cht_nozzle(def)`: finds `nozzle_type` in `def.options` (mutable; `ConfigDef::get()` returns const), returns if "cht" already in `enum_values`, else inserts `"cht"` and label `"CHT"` at index `min(int(ntCHT), size)`. |
| `src/libslic3r/Cosmyx/{BedTemperatureOff.*,IroningTemperature.*,ConfigDefExtensions.*,GCodeHooks.hpp,Cosmyx.cmake}`, `src/slic3r/GUI/Cosmyx/*` | Cosmyx-owned (foundation) | Foundation module; other features are stubs here. |
| `tests/cosmyx/test_cht_nozzle.cpp` | test | 7 cases (see Verification). |
| `wiki/decisions/0020..0022`, foundation `0001..0004`, `README.md` | docs | |
| `CHANGELOG.md`, `justfile`, `scripts/cosmyx/*`, `.github/workflows/cosmyx-checks.yml` | CI / docs (foundation) | Feature line under slot T2. |

## Rebase risk zones

Checked against `upstream/v2.5.1`. The hook patch applies cleanly on the v2.5.1 tree (`git apply --check`). The enum and string maps are identical in the tag: `NozzleType` has the same list (ends `ntBrass, ntE3D, ntCount`), `s_keys_map_NozzleType` at line 624 (631 in DEV), `NozzleTypeEumnToStr` at `PrintConfig.hpp` line 539 (570 in DEV), `nozzle_type` enum_values `undefine, hardened_steel, stainless_steel, tungsten_carbide, brass` (5 entries, so "cht" lands at index 5), `nozzle_info.json` version `1.0.0.3` with the same keys.

| File | DEV vs v2.5.1 | Commits since 2026-01-01 on DEV | Risk |
|---|---|---|---|
| `src/libslic3r/CommonDefs.hpp` | identical | 0 | Low, but this is the semantic risk: any upstream nozzle type inserted before `ntE3D` changes the position invariant. |
| `src/libslic3r/PrintConfig.hpp` | mid-file differences elsewhere (+4/-56) | 227 | Low (hook is inside a small map). |
| `src/libslic3r/PrintConfig.cpp` | large | 385 | Low for the map line, shared include/ctor hook. |
| `resources/info/nozzle_info.json` | identical keys | 1 | Low; a new upstream entry above `hardened_steel` merely moves the line. |

## Intent to preserve

- "CHT" appears in the printer settings `nozzle_type` combo, at the position equal to `int(NozzleType::ntCHT)`, because the GUI stores the combo position as the enum value. Picking CHT must save `nozzle_type = cht` and reload it as CHT.
- Round trip: `"cht"` <-> `ntCHT` in the config enum map and both string maps.
- Hardness of `cht` is 65; tungsten carbide stays 85; upstream types are unchanged.
- If upstream later adds its own CHT (or any nozzle type) to the enum, do not force the old lines: drop the duplicate hook lines, keep the upstream ones, make `extend_cht_nozzle` no-op (it already is when "cht" is in `enum_values`), and re-point the tests to upstream's enum value. If upstream inserts another type before `ntE3D`, place `ntCHT` at the next free choice position (= current number of choices in `nozzle_type.enum_values`) and keep the position test green; do not append after `ntE3D` unless `enum_values` position still equals the enum value.

## Verification

Catch2, suite `cosmyx_tests`, tag `[cosmyx][ChtNozzle]`, `tests/cosmyx/test_cht_nozzle.cpp`: "CHT sits at the position of its enum value in nozzle_type", "CHT keeps the upstream nozzle types", "CHT extender is idempotent", "CHT enum and string maps round-trip", "A config with nozzle_type cht loads and saves", "nozzle_info.json gives CHT and tungsten carbide their hardness", "Print reports the CHT hardness". Foundation cases `test_cosmyx_foundation.cpp` and `just test-scripts`. Run `ctest --test-dir build -C Release -R cosmyx`; build is by dispatching `build_all.yml` on the branch. Manual: Printer settings > Extruder > Nozzle type shows CHT; save and reload keeps it.

## Known pitfalls

- `08d8d62f96`: `ConfigDef::get()` returns a const pointer, so the first version (`def.get("nozzle_type")` assigned to `ConfigOptionDef*`) did not compile. Take the mutable definition from `def.options.find("nozzle_type")`.
- Do not append "cht" at the end of the choices: the position must equal the enum value (decision 0020).
- The JSON line has no `// Cosmyx` marker; do not drop it during a rebase of `resources/info/nozzle_info.json`.

## Shared files with other branches

- Foundation commits and stubs shared with all four sibling branches. This branch owns `ChtNozzle.cpp`; siblings carry a stub of it.
- `PrintConfig.cpp` line 2 include, ctor call and `GCode.cpp` line 2 include are identical across branches (identical hunks merge cleanly). `PrintConfig.cpp` also gets the `s_keys_map_NozzleType` line only here.
- `CHANGELOG.md`: slot T2. `wiki/decisions`: numbers 0020-0029. `tests/cosmyx/CMakeLists.txt` globs, no edit needed.
