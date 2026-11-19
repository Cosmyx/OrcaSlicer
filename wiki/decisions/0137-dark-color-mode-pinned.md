# 0137. The dark_color_mode config key is pinned to "1"

## Status

Accepted.

## Context

Forcing `GUI_App::dark_mode()` is not enough: about ten upstream places read
the `dark_color_mode` app config key directly (GLCanvas3D, GLTexture, Plater,
GUI_Utils, AboutDialog, TroubleshootDialog, PrivacyUpdateDialog, ...). Three
upstream sites write it:

- `GUI_App::on_init_inner()`, macOS and Linux: writes the system appearance
  (`"1"` or `"0"`), saves, then calls `dark_mode()`.
- `update_dark_config()` in `GUI_Utils.cpp`, on a system colour change: writes
  the system appearance, then calls `Update_dark_mode_flag()`, which calls
  `dark_mode()`.
- The Windows Preferences toggle: writes `"0"` or `"1"`, saves, then calls
  `Update_dark_mode_flag()`.

The default `"0"` in `AppConfig::set_defaults()` only applies on Windows and
only when the key is empty.

## Decision

- `Cosmyx::force_dark_color_mode(AppConfig&)` sets the key to `"1"` whatever
  it holds, and says whether it changed it. It is wxWidgets-free and tested in
  `tests/cosmyx/test_color_mode.cpp`.
- It runs from `AppConfig::set_defaults()`, outside the `#ifdef _WIN32`
  block, so every OS gets `"1"` after every load and reset: a saved `"0"`
  never reaches the GUI.
- It runs again each time `GUI_App::dark_mode()` is asked (decision 0138).
  Every write site above calls `dark_mode()` right after writing, so the key
  is healed before any direct reader sees `"0"`. No hook is placed at the
  write sites themselves.
- The healed value marks the config dirty but is not saved on the spot; a
  `"0"` left on disk by a write site is forced back at the next load anyway.
- Upstream hooks, each one line ending with `// Cosmyx`:
  - `src/libslic3r/AppConfig.cpp`, line 2: the include of
    `Cosmyx/ColorModeDefault.hpp`.
  - `AppConfig::set_defaults()`, right before the Windows-only
    `#ifdef _WIN32` block: `Cosmyx::force_dark_color_mode(*this);`.

## Consequences

- A new upstream site that writes the key without calling `dark_mode()`
  afterwards would leave direct readers light until the next `dark_mode()`
  call or restart. Check for new writes of `dark_color_mode` when merging
  upstream.
- Removing it: delete the two hook lines and `ColorModeDefault.{hpp,cpp}`.
