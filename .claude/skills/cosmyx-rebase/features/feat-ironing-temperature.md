# feat/ironing-temperature (PR #90)

## Purpose

Some filaments iron better cooler or hotter than they print. Upstream has per-filament ironing overrides for flow, spacing, inset and speed but not for temperature. This feature adds the filament option `filament_ironing_temperature` (Filament > Print temperature, advanced mode, 0 to 500, default 0 = no change). While ironing, the nozzle is set to that temperature (`M104`, no wait); when ironing ends the nozzle goes back to the first-layer or normal print temperature, including for a tool left right after ironing on multi-tool printers and for the wipe tower. Out-of-range values are refused by config validation, which also gives every future Cosmyx numeric option a range check. Decisions: 0030 to 0036. Changelog slot: T3 (libslic3r).

## Parent and dependencies

- Parent: `DEV`. Carries foundation commits `6cbd27d0fc`..`39c40f609f` (PR #86). Own commits: `dd1fe8beda` (feature), `bf375dc60c` tests, `868e7780c8` docs, `255f589fbc`, `1e69832f43` (range check), `100af33e62`, `f82a918cc5`, `9909209df0`, `685b434cb4`.
- No dependency on the other feature branches. It uses the foundation helper `Cosmyx::add_option()` and `is_cosmyx_option()` (`ConfigDefExtensions`), and `GCodeHooks.hpp`.
- Upstream symbols used: `GCode::m_last_extrusion_role` (written only by `_extrude_piece`), `GCode::on_first_layer()`, `GCode::get_filament_config_index()`, `GCode::config()`, `GCode::m_print->full_print_config()`, `GCodeWriter::filament()` and `set_temperature(temp, wait, tool)`, `WipeTowerIntegration` (friend of `GCode`), `ExtrusionRole erIroning`, `nozzle_temperature` and `nozzle_temperature_initial_layer` (variant-expanded), `s_Preset_filament_options`, `TabFilament::build()` and `append_single_option_line`, `ConfigOptionDef::is_value_valid`, `DynamicPrintConfig::validate()`, `Slic3r::validate()`, `serialization_key_ordinal`.

## Changes

| File | Kind | What it does |
|---|---|---|
| `src/libslic3r/Cosmyx/IroningTemperature.hpp` | Cosmyx-owned | Declares `ironing_temperature_key`, `ironing_temperature(full, filament_id)`, `any_ironing_temperature(full)`, `ironing_temperature_gcode(...)`, `ironing_temperature_toolchange_gcode(...)`. |
| `src/libslic3r/Cosmyx/IroningTemperature.cpp` | Cosmyx-owned | `extend_ironing_temperature(def)` adds `filament_ironing_temperature` with `add_option(def, key, coInts)`: label/tooltip, sidetext degrees C, min 0, max 500, `comAdvanced`, default `{0}`, not nullable. Plus the two config readers. Must not include GCode headers (see pitfalls). |
| `src/libslic3r/Cosmyx/IroningTemperatureGCode.cpp` | Cosmyx-owned | G-code helpers: entering `erIroning` with temperature > 0 emits `M104` without wait for that filament id; leaving ironing restores print temperature (first layer value on first layer, each falling back to the other when 0, nothing when both 0); the tool change helper restores the outgoing tool when the last path was ironing. Kept in its own file on purpose. |
| `src/libslic3r/Cosmyx/ConfigValidation.cpp` | Cosmyx-owned | `validate_option_ranges(config, errors)`: range check for Cosmyx numeric options (`coFloat, coPercent, coFloatOrPercent, coFloats, coPercents, coInt, coInts`) with the upstream message `"%1% not in range [%2%, %3%]"`. Declared in `ConfigDefExtensions.hpp`. |
| `src/libslic3r/GCode.cpp` | upstream hook | (a) line 2 `#include "Cosmyx/GCodeHooks.hpp" // Cosmyx`. (b) In `WipeTowerIntegration::tool_change(GCode &gcodegen, int extruder_id, bool finish_layer)`, right after `std::string gcode;`: `gcode += Cosmyx::ironing_temperature_toolchange_gcode(gcodegen, gcodegen.m_print->full_print_config(), gcodegen.m_last_extrusion_role, gcodegen.on_first_layer()); // Cosmyx`. (c) In `GCode::_extrude_piece`, immediately before `m_last_extrusion_role = path.role();`: `gcode += Cosmyx::ironing_temperature_gcode(*this, m_print->full_print_config(), m_last_extrusion_role, path.role(), this->on_first_layer()); // Cosmyx`. (d) In `GCode::set_extruder`, right after `std::string gcode = this->retract(true, false);` (below comment `prepend retraction on the current extruder`): `gcode += Cosmyx::ironing_temperature_toolchange_gcode(*this, m_print->full_print_config(), m_last_extrusion_role, this->on_first_layer()); // Cosmyx`. |
| `src/libslic3r/Preset.cpp` | upstream hook | In `s_Preset_filament_options`, between `"ironing_fan_speed",` and the comment `// Filament ironing overrides`: `"filament_ironing_temperature", // Cosmyx`. |
| `src/libslic3r/PrintConfig.cpp` | upstream hook | In the FFF branch of `DynamicPrintConfig::validate()`: `return Slic3r::validate(fpc, under_cli);` becomes `return Cosmyx::validate_option_ranges(*this, Slic3r::validate(fpc, under_cli)); // Cosmyx`. Plus foundation hooks (line 2 include, `extend_print_config_def` call). |
| `src/slic3r/GUI/Tab.cpp` | upstream hook | In `TabFilament::build()`, "Print temperature" group, right after `line.append_option(optgroup->get_option("nozzle_temperature", 0)); optgroup->append_line(line);`: `optgroup->append_single_option_line("filament_ironing_temperature", "", 0); // Cosmyx`. |
| `src/libslic3r/CMakeLists.txt`, `src/slic3r/CMakeLists.txt`, `tests/CMakeLists.txt` | upstream hook (foundation) | The three one-line `include`/`add_subdirectory` hooks tagged `# Cosmyx`. |
| `scripts/cosmyx/tests/test_libslic3r_link_closure.py` | test / CI | Refuses a Cosmyx libslic3r `.cpp` that both defines a `PrintConfigDef` extension and includes `libslic3r/GCode.hpp`, `GCodeWriter.hpp` or `GCode/`. |
| `tests/cosmyx/test_ironing_temperature.cpp`, `tests/cosmyx/test_breaker_ironing_temperature.cpp` | test | See Verification. |
| `wiki/decisions/0030..0036`, foundation docs | docs | |
| `CHANGELOG.md`, `justfile`, other foundation files | CI / docs | Line under slot T3. |

## Rebase risk zones

Hook patch applies cleanly on the `upstream/v2.5.1` tree (`git apply --check`). All anchors exist in the tag: `WipeTowerIntegration::tool_change(...)` followed by `std::string gcode;` (line 2092 in the tag, 2079 in DEV), `m_last_extrusion_role = path.role();` (once, line 9867 vs 9968), `std::string gcode = this->retract(true, false);` (11077 vs 11199), `"ironing_fan_speed",` and `"filament_ironing_flow", "filament_ironing_spacing"...` in `Preset.cpp` (1565/1567), `return Slic3r::validate(fpc, under_cli);` (line 10690 vs 10923), `nozzle_temperature` line in `Tab.cpp` (4882 vs 4905).

| File / function | Differs DEV vs v2.5.1 | Commits since 2026-01-01 on DEV |
|---|---|---|
| `GCode.cpp` (4 hooks) | Whole file differs; `set_extruder` differs: DEV has added `m_retract_after_last_path = false;` and moved the bare `T<n>` emission with a single-extruder temperature reset; `_extrude_piece` differs (DEV factored `path_slicing_point()` and `extrusion_mm3_per_mm()`, `m_sub_layer_flow_ratio`). The hook lines sit in unchanged statements. | 342 (highest churn) |
| `Preset.cpp` | small (+1/-17) | 239 |
| `PrintConfig.cpp` | large | 385 |
| `Tab.cpp` | +30/-52 | 424 |

APIs present in v2.5.1: all symbols listed above (`get_filament_config_index`, `on_first_layer`, `full_print_config`, `friend class WipeTowerIntegration` in `GCode.hpp`, `GCodeWriter::filament`/`set_temperature`, `serialization_key_ordinal`, `by_serialization_key_ordinal`, `is_value_valid`, `set_deserialize_strict`, `filament_ironing_flow`).

## Intent to preserve

- With the option at 0 (default) the G-code is byte identical to upstream.
- With a value > 0: one `M104 S<t>` (with `T<tool>` on multi-tool) when the first ironing path of a run starts, no wait; ironing end restores the print temperature of the tool now in use; a tool that irons last on a layer is restored to its print temperature before its tool change (`T`, `M1020`) and before wipe tower blocks, so pre-cooling lines inserted after tool change anchors are not undone (decision 0036).
- Variant handling: the option is not variant-expanded, indexed by filament id; the restore temperatures use `get_filament_config_index()`.
- Values outside 0..500 are refused in `DynamicPrintConfig::validate()`.
- The option is saved in filament presets (`s_Preset_filament_options`) and visible in the filament tab.
- If upstream rewrites `_extrude_piece` or `set_extruder`, re-hook at: the point where the role of the path to print is known and before its extrusion moves (role transitions), at the tool change entry before any `T` anchor, and at the wipe tower `tool_change()` entry. Keep a decision that role comparison uses `m_last_extrusion_role` (the processor role is forced to `erWipeTower` by the tower code). If upstream adds its own per-filament ironing temperature, drop the Cosmyx option and migrate presets using `filament_ironing_temperature`.

## Verification

- Catch2 `tests/cosmyx/test_ironing_temperature.cpp` (tag `[cosmyx]`): "filament_ironing_temperature is a filament option, off by default", "The ironing temperature is read per filament id", "One tool irons at the ironing temperature and prints at the print temperature", "An ironing temperature of 0 adds no temperature command", "A tool selected again after ironing prints at its print temperature", "A tool left after ironing is back at its print temperature before the tool change".
- Catch2 `tests/cosmyx/test_breaker_ironing_temperature.cpp` (tag `[cosmyx][breaker][IroningTemperature]`): "Config validation refuses an ironing temperature above its maximum", "...refuses a negative ironing temperature", "...accepts ironing temperatures inside the range".
- Foundation `[cosmyx]` cases (notably "Every Cosmyx option default is within its own range", "Upstream options keep their upstream ordinals").
- Script test: `scripts/cosmyx/tests/test_libslic3r_link_closure.py` via `just test-scripts`.
- CI: dispatch `build_all.yml` on the branch; Linux x86_64 and aarch64 builds are the proof that generate_system_cache etc. still link.
- Manual: set Filament > Print temperature > Ironing temperature to 190 with ironing enabled; the G-code shows `M104 S190` before the first ironing path and the print temperature after; two-tool print shows the restore before `T1`.

## Known pitfalls

- `685b434cb4` (libslic3r link closure): `PrintConfig.cpp` calls `Cosmyx::extend_print_config_def`, which pulls `IroningTemperature.o` into every program linking static libslic3r. When that file also called `GCode`/`GCodeWriter`, small tools such as `generate_system_cache` pulled `GCode.o` and the 3MF/SVG code and failed on Linux (x86_64 and aarch64) with undefined `nsvgParse`, `nsvgParseFromFile`, `nsvgDelete`. Rule: a Cosmyx file defining a `PrintConfigDef` extension must not include GCode headers; G-code helpers live in `IroningTemperatureGCode.cpp`. Enforced by the link closure script test.
- `1e69832f43` + decision 0035: `DynamicPrintConfig::validate()` copies the config into a static `FullPrintConfig`, which drops options added with `add_option()`, so `filament_ironing_temperature = 600` validated and reached the G-code. The sixth hook line fixes it.
- `100af33e62`: `DynamicPrintConfig::full_print_config()` holds only static keys; check the default option through the default filament preset / `PresetBundle::full_fff_config()` instead.
- `9909209df0`: `set_deserialize_strict({ {key, value} })` resolves to the `(key, value, bool)` overload and fails with a narrowing error; call the two-argument key/value form.
- Pre-cooling order (`f82a918cc5`, decision 0036): the restore must stay before the `T`/`M1020`/nozzle-change anchors the G-code processor injects after.
- Decision 0031: no `Print.cpp` hook is needed because the option is only in `full_config_diff`; re-check this if `PrintApply.cpp` changes how `m_full_print_config` refreshes.

## Shared files with other branches

- Foundation commits and stubs shared with all siblings; this branch owns `IroningTemperature.cpp/.hpp`, `IroningTemperatureGCode.cpp`, `ConfigValidation.cpp`. It edits `ConfigDefExtensions.hpp`? Only by declaring `validate_option_ranges` (foundation file; keep that declaration when merging with siblings that also touch it).
- `GCode.cpp`: also touched (one include) by every branch; ironing adds four more hooks. `fix/toolchange-fan-order` does not touch GCode.cpp beyond the include.
- `PrintConfig.cpp`: shares the `extend_print_config_def` hook with all; the `validate()` hook is only here; `feat/cht-nozzle` edits a different region of the same file.
- `scripts/cosmyx/tests/test_libslic3r_link_closure.py` is checked against every file in `src/libslic3r/Cosmyx/`, including siblings' (e.g. `ChtNozzle.cpp`, which must keep including only config headers).
- `CHANGELOG.md` slot T3, `wiki/decisions` 0030-0039, `tests/cosmyx/CMakeLists.txt` glob.
