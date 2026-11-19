# 0021. Device and BBL display maps left untouched for CHT

## Status

Accepted.

## Context

Besides the config maps, the GUI has nozzle type maps for connected Bambu Lab
printers (`DeviceCore/DevNozzleSystem.cpp`, `PrintOptionsDialog.cpp` and
others). They translate the type reported by a printer's firmware. No Bambu Lab
firmware reports a CHT nozzle.

## Decision

Only the config definition, the enum, the config string maps and the hardness
table learn about CHT. The device and BBL display maps are not edited.

## Consequences

- No extra upstream lines, so no extra merge conflict risk.
- A CHT nozzle is selectable and saved in printer settings and drives the
  hardness check through `Print::get_hrc_by_nozzle_type()`, but a device
  dialog for a Bambu Lab printer never shows it, which matches what the
  firmware can report.
- If a device map is ever needed, it is a new decision with its own hook.
