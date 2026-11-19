# 0036. The ironing restore and the multi-nozzle pre-cooling

## Status

Accepted.

## Context

On multi-nozzle printers with `enable_pre_heating`, the G-code processor's
second pass (`GCodeProcessor::run_second_pass_injection()`) inserts
"Multi extruder pre cooling" `M104` lines for a nozzle that goes idle. The
restore hooks of 0033 set a tool that ironed last back to its print temperature
at the tool change. If that `M104` came after the pre-cooling one, it would heat
the idle nozzle back up and undo the pre-cooling.

## Decision

No code change: the order is already right, and a test pins it.

- The injector inserts its lines after an anchor line of the finished G-code.
  With the wipe tower ("type 1", every BBL printer) the anchors are the
  `NOZZLE_CHANGE_START` and `NOZZLE_CHANGE_END` markers of the tower's nozzle
  change block (`build_by_extruder_blocks()`); without it they are the filament
  change lines `T`, `;VT` or `M1020` (`build_by_filament_blocks()`).
- The `WipeTowerIntegration::tool_change()` hook runs first in that function,
  before `append_tcr()` writes the retraction, the nozzle change block and the
  change filament G-code. The `set_extruder()` hook runs right after the tool
  change retraction, before the filament end G-code and the change filament
  G-code that holds `T` or `M1020`. So the restore always comes before every
  anchor, and the pre-cooling lines land after it.
- The restore also matches what the injector assumes: it computes the cooling
  from the outgoing filament's print temperature, which is the temperature the
  restore sets.
- The test `A tool left after ironing is back at its print temperature before
  the tool change` checks, on two tools with and without a prime tower, that the
  outgoing tool's target is its print temperature when the `T` line is reached.

## Consequences

- The test fixtures are not BBL printers, so the type 1 tower path is covered by
  reading the code, not by the test.
- A future upstream change that moves the anchors before the hooks (for example
  a nozzle change marker written before the retraction) would reopen the
  question; the test catches it only for the `T` line.
