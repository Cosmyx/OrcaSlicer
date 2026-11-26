# 0162. GUI goldens: an in-app driver and an external harness

## Status

Accepted.

## Context

The shared rules ask for every screen of every app to be pinned to a committed
image, and the user asked for GUI goldens on Windows, macOS and Linux: launch
the built application on a runner, capture every menu and dialog, and finish
with a slice driven from the interface. Upstream has no way to drive the GUI
from outside: NativeCommands has no external trigger, dialogs are modal, and
accessibility trees do not reach the custom-drawn wxWidgets controls.

## Decision

- An in-app driver (`src/slic3r/GUI/Cosmyx/GoldenDriver`) walks the
  application through `tests/cosmyx/gui/script.json` from a 50 ms timer, which
  keeps firing inside the nested loops of modal dialogs and popup menus on
  every toolkit. It opens surfaces through the application's own entry points
  (`NativeCommands::run`, `GUI_App::open_preferences`, `MainFrame::select_tab`,
  `Tab::activate_option`, `Plater::load_files`), never through synthetic clicks.
- Its wxWidgets-free half (`logic/GoldenScript`) parses the script, expands
  the generators and writes the protocol events; `cosmyx_tests` covers it.
- An external harness (`scripts/cosmyx/gui_goldens`) seeds the data folder,
  starts the build, captures the screen when asked and compares the captures
  with the committed goldens.

## Consequences

- One driver for three OSes, with no per-OS C++.
- Removing it: delete the two `GUI_App.cpp` hook lines (decision 0163), the
  `GoldenDriver` and `GoldenScript` files, `tests/cosmyx/test_golden_script.cpp`,
  `tests/cosmyx/gui/`, `scripts/cosmyx/gui_goldens/`, the workflow, the recipes
  and the wiki page.
