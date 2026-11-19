# 0022. Propose the CHT nozzle patch upstream

## Status

Accepted.

## Context

The CHT nozzle is carried as small hooks in upstream files
(`CommonDefs.hpp`, `PrintConfig.hpp`, `PrintConfig.cpp`,
`resources/info/nozzle_info.json`). Every carried hook is a possible conflict
when upstream merges into DEV.

## Decision

The same change (enum value before `ntE3D`, the three map entries, the
`nozzle_type` choice at its enum position and `"cht": 65` in
`nozzle_info.json`) is proposed to upstream OrcaSlicer as a pull request,
written in upstream's own style without the Cosmyx module.

## Consequences

- If upstream accepts it, the Cosmyx hooks and `extend_cht_nozzle()` become
  redundant: the extender already does nothing when "cht" is present, and the
  hook lines are then deleted from DEV in the merge that brings the upstream
  version, keeping upstream's lines.
- If upstream declines, the hooks stay as they are.
