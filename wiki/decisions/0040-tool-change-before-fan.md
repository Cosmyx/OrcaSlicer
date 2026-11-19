# 0040. Tool change before the new tool's fan command

## Status

Accepted.

## Context

`CoolingBuffer::apply_layer_cooldown()` handles a tool change line (`Tn`) by
first computing the new tool's fan speed, which writes its `M106` right away,
and only then copying the `Tn` line. The output reads `M106 S<new>` then `Tn`.

On printers with one part cooling fan per tool (Klipper toolchangers, IDEX
machines), `M106` drives the fan of the active tool. The command therefore
lands on the tool being parked, and the new tool prints with whatever fan
state it had, until the next fan change.

The tool change G-code (`GCode::set_extruder()` and the wipe tower's
`append_tcr()`) also writes a `;_FORCE_RESUME_FAN_SPEED` tag right before the
`Tn` line, because the change G-code may have changed the fan. The cooling pass
turns that tag into `M106 S<old>` at once, so the resume also lands on the tool
being parked.

An earlier Cosmyx branch fixed this inside the fan speed lambda. That fix is
not ported: it bypasses the speed deduplication the current code relies on
(`m_fan_speed` and `m_current_fan_speed`).

## Decision

- Copy the `Tn` line as the first step of the tool change branch, before the
  fan speed is computed and written. The output reads `Tn` then `M106 S<new>`.
- The line is copied whether or not its tool number parses, exactly as before.
- A fan resume whose next line is a tool change the cooling pass acts on (a
  tool number in range that differs from the active tool, the same test that
  makes the line `TYPE_SET_TOOL`) waits for that tool change. At the `Tn`, the
  pending resume marks the fan state as unknown, so the new tool's speed is
  written once after the `Tn` even when it equals the old one.
  `Cosmyx::resume_waits_for_tool_change()` in
  `src/libslic3r/Cosmyx/ToolChangeFan.cpp` holds the test.
- Deduplication, the deferred fan requests and the belt band handling are
  untouched: inside the belt band the fan still ends at 0 after the `Tn`.
- The hooks are the moved line, marked `// Cosmyx: Tn before fan`, one include
  after line 1 of `CoolingBuffer.cpp`, and two lines marked
  `// Cosmyx: resume after Tn` (the resume branch and the tool change branch).
- The change is generic and fixes upstream behaviour, so it is proposed
  upstream. Once upstream carries it, the Cosmyx hook goes away with the next
  sync.

## Consequences

- On single fan printers nothing changes for the print: the fan command moves
  one line, after the tool change instead of before it.
- `tests/cosmyx/test_toolchange_fan_order.cpp` pins the order, the resume after
  a change G-code that sets the fan, the single filament output, the belt band
  case and the resume test itself. Its two filament fixture sets
  `filament_extruder_variant` and `filament_self_index` for both filaments:
  the fan speeds are per variant options, and without those columns every
  filament reads the first filament's speeds.
- Removing the fix means moving the `new_gcode.append(...)` line back to the
  end of the tool change branch, restoring `need_set_fan = true;` in the
  resume branch, deleting the other hook lines, `ToolChangeFan.*` and the test
  file.
