# 0030. Ironing temperature option

## Status

Accepted.

## Context

Some filaments iron better a little cooler (or hotter) than they print. Upstream
has filament overrides for ironing flow, spacing, inset and speed, but none for
the temperature. Cosmyx options must not edit the static `PrintConfig` structs,
so the option exists only in `print_config_def` and in dynamic configs.

## Decision

- New filament option `filament_ironing_temperature`: `coInts`, not nullable,
  default `0`, range 0 to 500, `comAdvanced`, label "Ironing temperature",
  shown in the filament "Print temperature" group. `0` means no change, so the
  option is off for every existing profile and project.
- Not nullable: `0` already means "off", so a nil state would only add a
  second way to say the same thing, plus the override checkbox UI.
- G-code generation reads it by key from `Print::full_print_config()`
  (`Cosmyx::ironing_temperature()`), since `GCode::config()` has no member for
  it.
- It is indexed by filament id, not by `GCode::get_filament_config_index()`.
  The option is not variant-expanded (see 0032), so on a variant printer the
  config column can be past its end and `get_at()` would silently return
  filament 1's value. The nozzle temperatures it restores are variant-expanded
  and do use the config column, as upstream does.
- Entering an ironing path with a value above 0 emits
  `M104 S<t> [T<tool>]` without waiting. Leaving ironing restores the first
  layer temperature on the first layer and the normal temperature elsewhere
  (each falling back on the other when 0; nothing is emitted when both are 0,
  so the heater is never switched off).
- The role compared is `GCode::m_last_extrusion_role`, which only `_extrude`
  writes. The processor role is forced to `erWipeTower` by the tower code and
  would make a restore fire, or not, at the wrong place.

## Consequences

- No wait on the change: ironing starts while the nozzle drifts to the new
  target. A wait would park the nozzle over the top surface and ooze on it.
- Removing the feature: delete `src/libslic3r/Cosmyx/IroningTemperature.*`
  contents, its test, and the hook lines listed in 0034. Profiles that saved a
  value keep an unknown key, which the loader ignores.
