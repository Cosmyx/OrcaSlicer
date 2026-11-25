# 0063. Version hooks and the source of the patch number

## Status

Accepted.

## Context

The patch number must reach the C++ code and the CI script from one place,
without editing `version.inc` or `libslic3r_version.h.in`, which upstream
edits on every release. A compile definition set from `Cosmyx.cmake` would not
reach the `cosmyx_tests` suite, which compiles `logic/` without that file, and
the test CMake file belongs to the foundation.

## Decision

- The patch is `inline constexpr int patch_version` in
  `src/slic3r/GUI/Cosmyx/logic/CosmyxVersion.hpp`. The script reads that line;
  the C++ code and the tests include the header. No CMake change.
- `Cosmyx::display_version()` composes it with `SoftFever_VERSION`.
- Upstream hooks, each a single line ending with `// Cosmyx`:
  - `src/slic3r/GUI/GUI_App.cpp`, line 2: the include of the header.
  - `GUI_App::format_display_version()`: returns
    `Cosmyx::display_version()`. This covers the splash screen and the About
    dialog's copy button.
  - `src/slic3r/GUI/AboutDialog.cpp`: the version label uses
    `GUI_App::format_display_version()`.
  - `src/slic3r/GUI/NetworkTestDialog.cpp`, `get_studio_version()`: same.
  - `src/slic3r/GUI/TroubleshootDialog.cpp`: the version label under the logo,
    same.
- Left on `SoftFever_VERSION` on purpose: the log lines, the stored `version`
  app config key, the updater, 3MF and preset version checks, the post
  processing context, the G-code viewer export header, the scene benchmark,
  the troubleshoot "copy info" text and its upstream bug report link.

## Consequences

- Five one-line edits of upstream files; each reverts by itself.
- Raising the patch is a one-line change in the header; the tests check it
  stays at 8 or above.
