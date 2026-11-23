# 0165. Native screen capture, one backend per OS

## Status

Accepted.

## Context

Captures must include what the application draws outside wxWidgets: window
frames, native menus, popup menus and system WebViews. Each OS has its own
capture API, so this is an OS exception to the OS-neutral rule.

## Decision

- Behind one interface, `scripts/cosmyx/gui_goldens/capture.py`:
  - Linux: `xwd -root` cropped to the rectangle; a popup menu is the topmost
    viewable override-redirect window (`xwininfo`); Escape through `xdotool`.
  - macOS: `screencapture -x -o -t png -R` in points; the menu bar is opened
    with System Events and a menu window found with
    `CGWindowListCopyWindowInfo` through JavaScript for Automation (stock on
    macOS, no compiled helper); Escape through System Events.
  - Windows: GDI `BitBlt` with a per-monitor DPI aware process; a popup menu
    is the visible `#32768` window; Escape through `keybd_event`.
- No `if os ==` outside `capture.py` and `launch.py`.

## Consequences

- Each backend is tested with fake tools on every OS, and with one real
  capture on its own OS when the OS allows it (the macOS test checks Screen
  Recording with `CGPreflightScreenCaptureAccess`, which never prompts, and
  skips with the reason otherwise).
- Removing an OS: delete its two modules and its matrix entry.
