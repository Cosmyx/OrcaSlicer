# 0054. Menu icon on every OS

## Status

Accepted.

## Context

The previous branch set the `menu_add_part_cosmyx` icon on Windows only, as
upstream did for its own menu items at the time. Upstream now passes its menu
icons on every OS.

## Decision

The "Cosmyx 3D Models" item and its three group submenus use
`menu_add_part_cosmyx` on every OS. There is no platform check in the code.

## Consequences

None beyond the icon showing on macOS and Linux too. The icon file is the one
shipped by the previous branch, unchanged.
