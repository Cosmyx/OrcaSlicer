# 0180. The user data folder lives under a Cosmyx vendor folder on every OS

## Status

Accepted, amended by 0184.

## Context

Upstream OrcaSlicer keeps its user data (presets, app config, login token,
plugins, logs) in a folder named after `SLIC3R_APP_KEY` ("OrcaSlicer") right
under the per-user data root. A Cosmyx build installed next to upstream
OrcaSlicer would read and write the same folder, so one would change the
other's presets and sign-in.

## Decision

- Every OS nests the data folder under a `Cosmyx` folder; the data folder name
  stays `SLIC3R_APP_KEY`:
  - Windows: `%APPDATA%\Cosmyx\OrcaSlicer`;
  - macOS: `~/Library/Application Support/Cosmyx/OrcaSlicer`;
  - Linux: `$XDG_CONFIG_HOME/Cosmyx/OrcaSlicer` (`~/.config/Cosmyx/OrcaSlicer`),
    and the same inside the Flatpak sandbox
    (`~/.var/app/<app id>/config/Cosmyx/OrcaSlicer`).
- Windows and macOS: `GUI/Cosmyx/AppPaths.cpp` sets the wx vendor name to
  `Cosmyx` and makes `wxStandardPaths` use both the vendor and the app name,
  so `GetUserDataDir()` returns the nested folder for every caller (the data
  folder in `GUI_App::init_app_config()` and the token fallback file of
  `OrcaCloudServiceAgent`).
- Linux: `default_data_dir()` builds the folder with
  `xdg_config_dir(Cosmyx::vendor_app_subdir(SLIC3R_APP_KEY))`, and
  `check_old_linux_datadir()` compares against the same path. The vendor
  setting also moves `GetUserDataDir()` on Linux from `~/.OrcaSlicer` to
  `~/.Cosmyx/OrcaSlicer`, so the token fallback file never meets upstream's.
- No migration from the un-nested folder: a Cosmyx build starts fresh (user
  decision). That includes upstream's Flatpak legacy data migration, which is
  skipped for the Cosmyx data folder (decision 0184). A portable `data_dir` folder next to the executable and
  `--datadir` still take precedence, as upstream.

## Consequences

- Users of a Cosmyx build that used the upstream folder set up their presets,
  login and plugins again. Cosmyx builds that already used
  `Cosmyx\OrcaSlicer` (the CosmoSlice builds) on Windows and macOS keep their
  data, since the path is the same.
- The wx vendor setting may also move other per-user wx folders, for example
  the local data folder the WebView2 runtime may use on Windows; they end up
  under `Cosmyx` too.
- Shared with upstream still: the file association ProgID, the D-Bus instance
  names, the bundle and Flatpak ids.
- Removing it: delete `src/libslic3r/Cosmyx/DataDir.*`,
  `src/slic3r/GUI/Cosmyx/AppPaths.*` and the hook lines listed in decision
  0181; the build uses the upstream folder again.
