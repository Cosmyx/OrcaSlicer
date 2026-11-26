# 0170. Every pass starts from a seeded data folder

## Status

Accepted.

## Context

A runner's own settings, the setup wizard, upgrade notices, tips, the splash
screen and update checks would all reach the captures.

## Decision

- `tests/cosmyx/gui/fixtures/OrcaSlicer.conf.in` becomes
  `<datadir>/<SLIC3R_APP_KEY>.conf`: wizard finished, the built version (no
  upgrade notice), no daily tips, no splash screen, en_US, expert mode, an
  update URL that points nowhere (`127.0.0.1:9`), a fixed geometry, and pinned
  Voron 2.4 350 / 0.20mm Standard / Generic PLA presets (no vendor network
  plugin prompts). The folder is emptied in place, never deleted.
- The app starts with `--datadir`; the driver sets the client size to
  1280x800 and clears notifications before each capture.
- The model fixture is a model the application ships
  (`resources/handy_models/OrcaCube_v2.drc`), so no asset is added.

## Consequences

- The seeded config is the only state a pass starts from.
