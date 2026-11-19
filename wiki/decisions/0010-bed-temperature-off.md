# 0010. Bed temperature -1 turns the bed off

## Status

Accepted.

## Context

Cosmyx printers need a filament profile that prints with the bed heater off.
Upstream bed temperature options (`*_plate_temp`, `*_plate_temp_initial_layer`)
accept 0 and up, and 0 already means "this filament does not support this
plate": `Print::validate()` refuses the print and the G-code result lists the
filament as not printable on that plate.

## Decision

- -1 means "bed heater off". Every option whose key ends with `_plate_temp` or
  `_plate_temp_initial_layer` gets `min = -1`, matched by pattern so a plate
  type added upstream is covered too.
- 0 keeps its upstream meaning, unchanged.
- `GCodeWriter::set_bed_temperature()` turns -1 into `M140 S0` and never waits
  (`wait = false`), so -1 never produces `M190`. Waiting for a bed that is
  switched off would at best do nothing and at worst hang on firmware that waits
  for cooling.
- The writer writes `M140 S0` once even on a fresh writer, whose state assumes
  a bed already at 0: the bed may still be hot from a previous print, so it is
  switched off explicitly. Further -1 requests write nothing while it stays off.
- The start and custom G-code placeholders `bed_temperature`,
  `bed_temperature_initial_layer`, `bed_temperature_initial_layer_single` and
  `first_layer_bed_temperature` are clamped to 0 right after GCode.cpp sets
  them, so a template such as `M190 S[bed_temperature_initial_layer_single]`
  never writes `S-1`.
- With the `by_highest_temp` formula, upstream takes the maximum starting from
  0, so a plate where every filament is -1 yields 0 there. The writer then sees
  0 and keeps upstream's behaviour for it (no line on a fresh writer).

## Consequences

- Hooks: the first statement of `GCodeWriter::set_bed_temperature()` and one
  call after the `first_layer_bed_temperature` placeholder in GCode.cpp, both
  marked `// Cosmyx`.
- A user template that hard-codes `M190 S{...}` still writes `M190 S0`; it is
  the template's choice and returns at once on common firmware.
- Removing the feature: delete the two hook lines, empty
  `extend_bed_temperature_off()` and `clamp_bed_temperature_placeholders()`,
  and delete `tests/cosmyx/test_bed_temperature_off.cpp`. Profiles saved with
  -1 then fail validation ("not in range") until set back to 0 or more.
