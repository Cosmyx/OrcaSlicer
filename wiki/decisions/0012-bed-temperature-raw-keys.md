# 0012. Raw plate keys and header comments keep -1

## Status

Accepted.

## Context

Templates can also read the plate options directly (`[hot_plate_temp]`,
`{cool_plate_temp_initial_layer[0]}`), and the G-code header writes
`; first_layer_bed_temperature = ...` for firmware that reads it. Clamping
those would mean hooking the print config itself or more upstream lines.

## Decision

Only the four derived placeholders are clamped (decision 0010). The raw plate
keys keep the configured -1, and the header comment written from the
`by_first_filament` formula may read -1.

## Consequences

- A template that reads a raw plate key must handle -1 itself, for example
  `{max(0, hot_plate_temp[0])}`. A test pins this behaviour.
- Firmware that heats from the header comment (for example Anycubic GoKlipper)
  receives -1; Cosmyx printers do not read it.
- Clamping them later is a new decision with its own hook.
