# 0174. Surfaces, ids and generators

## Status

Accepted.

## Context

The set of screens must be complete and must follow the application when
upstream adds a menu item, a settings page or a command.

## Decision

- Surface ids are `NN-slug`, by section: 00 start, 10 main tabs, 20 menus,
  30 command dialogs on an empty plate, 40 Preferences tabs, 50 the loaded
  model and every settings page, 60 the first screen of each calibration,
  70 selection, context menu and object or view commands, 90 the UI slice
  (Preview, layer slider, the G-code checked by T13 `slice.py`), 99 skipped
  commands with no section.
- Generators expand at run time from what the application reports: every
  menu (top bar popups on Windows and Linux, menu bar titles on macOS), every
  Preferences tab, every visible settings page, every classified command.
- `surfaces.txt` (every surface with its capture kind or skip reason) and
  `20-menu-tree.txt` (every menu item with its state) are text goldens, so a
  new or removed surface fails even before its image is looked at.

## Consequences

- Every upstream UI change moves goldens; they are refreshed in the merge
  pull request.
