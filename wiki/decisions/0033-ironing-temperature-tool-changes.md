# 0033. Restoring the temperature of a tool left after ironing

## Status

Accepted.

## Context

Ironing is the last thing a filament prints on an object's layer, so a tool
change often follows it. The restore in `_extrude` runs before the next path,
which then belongs to the new tool: the old tool would stay at its ironing
temperature, and nothing upstream sets it back when it is selected again (no
ooze prevention, no preheat). The plan made a two-tool test mandatory and named
a fallback hook in `GCode::set_extruder()` if reading the code showed the test
would fail. It did: on a two-nozzle printer without ooze prevention,
`set_extruder()` sets no temperature for the incoming tool.

## Decision

- Fallback taken: one more hook in `GCode::set_extruder()`, in the
  multi-extruder path right after the tool change retraction, calls
  `Cosmyx::ironing_temperature_toolchange_gcode()`. When the last path was
  ironing at an ironing temperature above 0, it sets the outgoing tool back to
  its print temperature (with its `T` index) before the tool change. Ooze
  prevention, which runs after it, still drops that tool to standby as before.
- Beyond the plan, a second extra hook: the wipe tower G-code
  (`WipeTowerIntegration::tool_change()`) is not printed through `_extrude`, so
  a tool that ironed last on a layer would print its tower block (or its part
  of a tool change on the tower) at the ironing temperature. The same helper is
  called at the start of `tool_change()`. It covers both tower types, including
  the BBL "type 1" path that changes tools without `set_extruder()`. The plan's
  test list asks for the print temperature to be back "across a wipe-tower
  layer", which this hook is what delivers.
- The restore in `_extrude` fires whenever ironing ends and any filament irons
  at its own temperature, for the tool now in use. On a single nozzle this sets
  the heater to the new filament's print temperature after a change from an
  ironing filament. On several nozzles, and when the tower hook already restored
  the tool, it costs one or two redundant `M104` with the same value: the hooks
  keep no state, so they cannot know another one already ran.

## Consequences

- Known limits, not covered:
  - If the first path after a tool change is itself ironing, the incoming tool
    irons at its print temperature (the role does not change). Ironing uses the
    top surface filament, which prints the surface just before, so this needs an
    unusual filament assignment.
  - The single-extruder path of `set_extruder()` (one tool, several filaments
    without `T` commands) has no hook; the `_extrude` restore covers it.
- Removing the fallback: delete the `set_extruder()` and `tool_change()` hook
  lines; the two-tool test then fails.
