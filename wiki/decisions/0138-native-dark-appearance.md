# 0138. GUI_App::dark_mode() is forced and the native appearance is dark

## Status

Accepted.

## Context

On macOS, upstream `GUI_App::dark_mode()` ignores the config and asks the
system (`mac_dark_mode()`); on Linux it falls back to the system when the key
is empty. Native widgets on macOS and GTK also follow the system appearance,
so a light system would draw light native controls under dark Orca colours.

The wxWidgets fork the dependencies build (OrcaSlicer/Orca-deps-wxWidgets at
`b44c39c100975a0ac0e46f937aa3f3eae5e18631`, wxWidgets 3.3) has
`wxApp::SetAppearance(wxApp::Appearance::Dark)`: on Cocoa it sets
`NSApp.appearance` to DarkAqua (macOS 10.14 and later), on GTK 3 it asks for
the "prefer dark" colour scheme. So no Objective-C fallback is needed.

## Decision

- `GUI_App::dark_mode()` returns true at once, right after
  `#ifdef SUPPORT_DARK_MODE`, through `Cosmyx::force_dark_mode()`. The
  upstream body below it stays as it is and is no longer reached.
- `Cosmyx::force_dark_mode()` (`src/slic3r/GUI/Cosmyx/ColorMode.cpp`) heals
  the config key (decision 0137) and, on macOS and Linux only, calls
  `wxTheApp->SetAppearance(Dark)` once, from the main thread, logging a
  warning if wxWidgets reports a failure. The first call happens in
  `GUI_App::on_init_inner()`, before any window is built.
- OS exception: the `#ifndef _WIN32` around the appearance call. Windows
  already gets its native dark mode from upstream NppDarkMode, which is driven
  by `dark_mode()`; calling `SetAppearance` there as well would mix two dark
  mode systems. The exception sits in this one file only.
- Upstream hooks, each one line ending with `// Cosmyx`:
  - `src/slic3r/GUI/GUI_App.cpp`, line 3, under the version include: the
    include of `Cosmyx/ColorMode.hpp`.
  - `GUI_App::dark_mode()`: `if (Cosmyx::force_dark_mode()) return true;`.

## Consequences

- On GTK, a theme without a dark variant keeps light native widgets; the Orca
  drawn parts are still dark. Nothing more can be done without shipping a
  theme.
- The appearance call is not covered by the unit tests (it needs a running
  wxApp); the CI builds check it compiles on each OS.
- Removing it: delete the two hook lines and `ColorMode.{hpp,cpp}`.
