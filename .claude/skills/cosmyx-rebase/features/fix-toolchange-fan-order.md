# fix/toolchange-fan-order (PR #91)

## Purpose

On printers with one part cooling fan per tool (Klipper toolchangers, IDEX), `M106` drives the fan of the active tool. The cooling pass (`CoolingBuffer::apply_layer_cooldown()`) wrote the new tool's `M106 S<new>` before copying its `Tn` line, so the speed landed on the tool being parked. Also, the tool change G-code writes `;_FORCE_RESUME_FAN_SPEED` right before `Tn`, which the cooling pass turned into `M106 S<old>` at once, again on the parked tool. The fix writes `Tn` first, then the new tool's fan speed, and holds a fan resume back until after a tool change that follows it. Single-fan printers print identically (the command only moves one line). The change is generic and is proposed upstream. Decision: 0040. Changelog slot: T4 (libslic3r).

## Parent and dependencies

- Parent: `DEV`. Carries foundation commits `6cbd27d0fc`..`39c40f609f` (PR #86). Own commits: `f8cfb1c4e5` (test first), `4043540b28` (fix), `e9ab15ae0f` (resume after Tn, test fixture fix).
- No dependency on other feature branches. The earlier Cosmyx fix inside the fan-speed lambda is intentionally not ported (it bypassed `m_fan_speed`/`m_current_fan_speed` deduplication).
- Upstream symbols used: `CoolingBuffer::apply_layer_cooldown`, `CoolingLine::TYPE_SET_TOOL`, `TYPE_FORCE_RESUME_FAN`, `fan_speed_change_requests`, `m_toolchange_prefix`, `m_current_extruder`, `m_num_extruders`, `m_current_fan_speed`, `m_fan_speed`, `change_extruder_set_fan`, `m_belt_band_active`, `need_set_fan`; `GCode::set_extruder` and wipe tower `append_tcr()` write the `;_FORCE_RESUME_FAN_SPEED` tag.

## Changes

| File | Kind | What it does |
|---|---|---|
| `src/libslic3r/Cosmyx/ToolChangeFan.hpp`, `ToolChangeFan.cpp` | Cosmyx-owned | `resume_waits_for_tool_change(next_line, prefix, current_tool, tool_count)`: true when the G-code following a resume tag starts with `prefix` + a tool number below `tool_count` different from `current_tool`, mirroring the `TYPE_SET_TOOL` classification (`from_chars`, only a missing number rejects; out of range reads as tool 0). |
| `src/libslic3r/GCode/CoolingBuffer.cpp` | upstream hook | Line 2 (after `#include "../GCode.hpp"`): `#include "libslic3r/Cosmyx/ToolChangeFan.hpp" // Cosmyx`. In `apply_layer_cooldown`, branch `if (line->type & CoolingLine::TYPE_SET_TOOL) {`: first statement `new_gcode.append(line_start, line_end - line_start); // Cosmyx: Tn before fan` (the original `new_gcode.append(line_start, line_end - line_start);` at the end of the branch is removed, i.e. the line is moved). Inside `if (new_extruder != m_current_extruder) {` after `m_current_extruder = new_extruder;`: `if (std::exchange(fan_speed_change_requests[CoolingLine::TYPE_FORCE_RESUME_FAN], false)) m_current_fan_speed = -1; // Cosmyx: resume after Tn`, before `change_extruder_set_fan(true);`. In `else if (line->type & CoolingLine::TYPE_FORCE_RESUME_FAN) {`: upstream `need_set_fan = true;` after `fan_speed_change_requests[CoolingLine::TYPE_FORCE_RESUME_FAN] = true;` becomes `need_set_fan = !Cosmyx::resume_waits_for_tool_change(std::string_view(line_end, gcode.c_str() + gcode.size() - line_end), m_toolchange_prefix, m_current_extruder, m_num_extruders); // Cosmyx: resume after Tn`. |
| `src/libslic3r/GCode.cpp`, `src/libslic3r/PrintConfig.cpp`, three CMakeLists | upstream hook (foundation) | Same foundation hooks as every branch (line 2 includes, `extend_print_config_def` call, `include(...)`/`add_subdirectory(cosmyx)` lines tagged `Cosmyx`). |
| `src/libslic3r/Cosmyx/{BedTemperatureOff.*,ChtNozzle.cpp,IroningTemperature.*,ConfigDefExtensions.*,GCodeHooks.hpp,Cosmyx.cmake}`, `src/slic3r/GUI/Cosmyx/*` | Cosmyx-owned (foundation) | Stubs of the other features. |
| `tests/cosmyx/test_toolchange_fan_order.cpp` | test | 5 cases (see Verification). |
| `wiki/decisions/0040-tool-change-before-fan.md` | docs | |
| `CHANGELOG.md`, `justfile`, `scripts/cosmyx/*`, `.github/workflows/cosmyx-checks.yml` | CI / docs (foundation) | Line under slot T4 (PR link `#91`). |

## Rebase risk zones

`CoolingBuffer.cpp` is the only feature hook file; it is a low-churn file (22 commits since 2026-01-01 on DEV) but DEV and v2.5.1 differ a lot (DEV +257/-17 lines, mostly code elsewhere in the file). The three hook sites are identical in v2.5.1: the `TYPE_SET_TOOL` branch (`new_gcode.append(...)` is last in the branch at line ~924 in the tag, `change_extruder_set_fan(true);` at 919), the resume branch (`TYPE_FORCE_RESUME_FAN] = true; need_set_fan = true;` at 968), and `m_belt_band_active` exists in both. The patch applies cleanly on the v2.5.1 tree (`git apply --check`). Foundation files carry the usual risks (see the sibling docs): `GCode.cpp` 342 commits, `PrintConfig.cpp` 385.

Upstream APIs: `std::from_chars`, `m_toolchange_prefix`, `m_num_extruders`, `CoolingLine::TYPE_FORCE_RESUME_FAN` all present in the tag; `;_FORCE_RESUME_FAN_SPEED` is still written by tool change G-code.

## Intent to preserve

- In the final G-code, no fan command (`M106`/`M107`) sits between the last extrusion of the old tool and the new `Tn`; the new tool's fan speed follows the `Tn`.
- A change G-code that sets the fan: after `Tn` the new tool's speed is written once (the fan state is marked unknown at the `Tn`) even when equal to the old speed.
- A resume followed by a `Tn` the cooling pass ignores (out of range, same tool, unparsable) is not swallowed: it still resumes at once.
- Deduplication of fan speeds, deferred requests and belt band handling are unchanged: inside the belt band the fan still ends at 0 after `Tn`. Single-filament output unchanged.
- If upstream rewrites `apply_layer_cooldown`, re-implement the behaviour rather than the lines: (1) copy the tool change line to the output before computing/writing the new tool's fan speed; (2) defer a force-resume request that precedes a tool change until after the `Tn`. If upstream fixes the order itself (the PR is proposed upstream), drop the hooks and `ToolChangeFan.*` and keep the test.

## Verification

Catch2 `tests/cosmyx/test_toolchange_fan_order.cpp`, tag `[cosmyx][Cooling]`: "The new tool's fan command follows its tool change", "The fan comes back after the tool change when the change G-code sets it", "A fan resume waits only for a tool change the cooling pass acts on", "A single filament print keeps one fan speed and no tool change", "A tool change inside the belt band leaves the fan off". Foundation cases and `just test-scripts`. Run `ctest --test-dir build -C Release -R cosmyx`; CI: dispatch `build_all.yml` on the branch. On failure the tests print the G-code around each tool change. Manual: slice two cubes on two filaments with fan speeds 30% and 80% and read the lines around `T1`.

## Known pitfalls

- `e9ab15ae0f`: CI showed no fan command after `T1` and `M106 S76` right before it. Test fixture cause: `fan_min_speed`/`fan_max_speed` are per-variant options whose columns follow `filament_extruder_variant` and `filament_self_index`; `set_num_filaments()` leaves them at one filament, so both filaments read the first column and no fan change was due. The fixture must set both arrays for two filaments. Product cause: the resume tag (see Purpose), fixed with `resume_waits_for_tool_change`.
- Do not "fix" it inside the fan speed lambda: it defeats `m_fan_speed`/`m_current_fan_speed` deduplication (decision 0040).
- The `Tn` line must be copied even when its number does not parse, as before.
- `resume_waits_for_tool_change` must stay in sync with the `TYPE_SET_TOOL` classification in `parse_layer_gcode`; re-check it if upstream changes that classification.

## Shared files with other branches

- Foundation commits and stubs shared with all siblings; this branch owns `ToolChangeFan.*`. It does not add a line to `GCodeHooks.hpp` (CoolingBuffer.cpp includes its header directly), so it never conflicts with the ironing and bed-temperature edits there.
- `CHANGELOG.md` slot T4, `wiki/decisions` 0040-0049, `tests/cosmyx/CMakeLists.txt` glob (no edit).
- `GCode.cpp` and `PrintConfig.cpp`: only the identical foundation hooks.
