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

An earlier Cosmyx branch fixed this inside the fan speed lambda. That fix is
not ported: it bypasses the speed deduplication the current code relies on
(`m_fan_speed` and `m_current_fan_speed`).

## Decision

- Copy the `Tn` line as the first step of the tool change branch, before the
  fan speed is computed and written. The output reads `Tn` then `M106 S<new>`.
- The line is copied whether or not its tool number parses, exactly as before.
- Deduplication, the deferred fan requests and the belt band handling are
  untouched: inside the belt band the fan still ends at 0 after the `Tn`.
- The hook is the moved line itself, marked `// Cosmyx: Tn before fan`.
- The change is generic and fixes upstream behaviour, so it is proposed
  upstream. Once upstream carries it, the Cosmyx hook goes away with the next
  sync.

## Consequences

- On single fan printers nothing changes for the print: the fan command moves
  one line, after the tool change instead of before it.
- `tests/cosmyx/test_toolchange_fan_order.cpp` pins the order, the single
  filament output and the belt band case.
- Removing the fix means moving the `new_gcode.append(...)` line back to the
  end of the tool change branch and deleting the test file.
