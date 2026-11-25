# 0032. The ironing temperature is not a per-variant option

## Status

Accepted.

## Context

Filament options listed in `filament_options_with_variant` (PrintConfig.cpp)
hold one value per filament and extruder variant, and are expanded when a
printer has several variants. Adding a key to that set means editing an
upstream list that changes often.

## Decision

`filament_ironing_temperature` is not added to `filament_options_with_variant`.
It holds one value per filament, like the upstream ironing overrides
(`filament_ironing_speed` and the others), and is read by filament id (0030).

## Consequences

- A filament cannot iron at a different temperature on each nozzle variant.
- Making it per-variant later: add the key to `filament_options_with_variant`
  (an upstream hook) and read it with `get_filament_config_index()`.
