# 0034. Ironing temperature hooks in upstream files

## Status

Accepted.

## Context

Decision 0002 limits upstream edits to one-line hooks next to stable lines.

## Decision

The feature has five hook lines, each ending with `// Cosmyx`:

- `src/libslic3r/GCode.cpp`, `GCode::_extrude_piece()`, right before
  `m_last_extrusion_role = path.role();`:
  `gcode += Cosmyx::ironing_temperature_gcode(*this, m_print->full_print_config(), m_last_extrusion_role, path.role(), this->on_first_layer());`
  It runs after the travel to the path and before the role tag and the
  extrusion moves.
- `src/libslic3r/GCode.cpp`, `GCode::set_extruder()`, right after
  `std::string gcode = this->retract(true, false);`:
  `gcode += Cosmyx::ironing_temperature_toolchange_gcode(*this, m_print->full_print_config(), m_last_extrusion_role, this->on_first_layer());`
  (see 0033).
- `src/libslic3r/GCode.cpp`, `WipeTowerIntegration::tool_change()`, right
  after its `std::string gcode;`:
  `gcode += Cosmyx::ironing_temperature_toolchange_gcode(gcodegen, gcodegen.m_print->full_print_config(), gcodegen.m_last_extrusion_role, gcodegen.on_first_layer());`
  (see 0033; `WipeTowerIntegration` is a friend of `GCode`).
- `src/libslic3r/Preset.cpp`, `s_Preset_filament_options`, between
  `"ironing_fan_speed",` and the `// Filament ironing overrides` comment:
  `"filament_ironing_temperature",`, so filament presets store it.
- `src/slic3r/GUI/Tab.cpp`, `TabFilament::build()`, after the nozzle
  temperature line of the "Print temperature" group:
  `optgroup->append_single_option_line("filament_ironing_temperature", "", 0);`

The first layer test is the per-layer `on_first_layer()`, the one
`set_extruder()` uses for the same temperatures.

## Consequences

- No new include: `GCode.cpp` sees the helpers through `Cosmyx/GCodeHooks.hpp`.
- Removing the feature removes these five lines.
