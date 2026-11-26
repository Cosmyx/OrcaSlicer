# 0136. Dark mode is always on

## Status

Accepted.

## Context

The Cosmyx build must look clearly different from OrcaSlicer at first sight.
Upstream starts in light mode on Windows (`dark_color_mode` defaults to `"0"`
there) and follows the system appearance on macOS and Linux. The first plan
made dark the default for fresh installs only, kept the system appearance for
existing configs, and left a way back to light. The user overrode that plan:
dark mode is forced for everyone and cannot be turned off.

## Decision

- The application is dark on Windows, macOS and Linux, for fresh installs and
  for existing configs, whatever the system appearance.
- There is no way back to light: no setting, no config key, no Preferences
  item. The Windows "Enable dark Mode" toggle has no effect (decision 0139).
- The policy is split in two halves: `src/libslic3r/Cosmyx/ColorModeDefault`
  pins the config value (decision 0137), and `src/slic3r/GUI/Cosmyx/ColorMode`
  forces `GUI_App::dark_mode()` and the native appearance (decision 0138).

## Consequences

- Users who need a light interface cannot get one from this build.
- Removing it: delete the two module pairs, the four hook lines listed in
  decision 0137 and 0138, and `tests/cosmyx/test_color_mode.cpp`. Upstream
  behaviour then comes back unchanged.
