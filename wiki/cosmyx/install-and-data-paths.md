# Install and data folders

A Cosmyx build keeps everything it installs and everything it writes under a
`Cosmyx` folder, so it lives side by side with an upstream OrcaSlicer install
on the same machine without sharing presets, sign-in or plugins.

Decisions: 0180 (data folder), 0181 (hooks), 0182 (Windows installer),
0183 (removal of an earlier Cosmyx install), 0184 (no legacy data migration),
0185 (upstream data folder test hook).

## User data folder

| OS | Cosmyx build | Upstream OrcaSlicer |
|----|--------------|---------------------|
| Windows | `%APPDATA%\Cosmyx\OrcaSlicer` | `%APPDATA%\OrcaSlicer` |
| macOS | `~/Library/Application Support/Cosmyx/OrcaSlicer` | `~/Library/Application Support/OrcaSlicer` |
| Linux | `$XDG_CONFIG_HOME/Cosmyx/OrcaSlicer` (default `~/.config/Cosmyx/OrcaSlicer`) | `~/.config/OrcaSlicer` |
| Linux Flatpak | `~/.var/app/<app id>/config/Cosmyx/OrcaSlicer` | `~/.var/app/<app id>/config/OrcaSlicer` |

The folder holds the app config, presets, the login token fallback file,
downloaded plugins, logs and caches. Its name stays `OrcaSlicer`
(`SLIC3R_APP_KEY`); only the `Cosmyx` parent is added.

As upstream, two things override it:

- a `data_dir` folder next to the executable (portable install; on macOS next
  to the `.app` bundle);
- the `--datadir <folder>` command-line option.

### Fresh start, no migration

A Cosmyx build does not copy anything from the un-nested `OrcaSlicer` folder.
After updating from a Cosmyx build that used it, set up the presets, sign in
and let the plugins download again, or copy the old folder's content into the
new one by hand while the app is closed.

Cosmyx builds that already used `Cosmyx\OrcaSlicer` on Windows and macOS (the
CosmoSlice builds) keep their data: the path is the same.

This holds for Flatpak too: upstream copies the data of its legacy Flatpak id
(`~/.var/app/io.github.softfever.OrcaSlicer/config/OrcaSlicer`) into a missing
data folder on first start, and a Cosmyx build skips that copy for its
`Cosmyx/OrcaSlicer` folder (decision 0184). No other upstream code copies a
legacy data folder on Windows, macOS or Linux.

### Other per-user folders

- `GetUserDataDir()` of wxWidgets also moves, for every caller: on Linux it is
  `~/.Cosmyx/OrcaSlicer` instead of `~/.OrcaSlicer` (only the login token
  fallback file uses it there).
- Temporary files stay in the system temp folder.

## Windows installer

| | Cosmyx build | Upstream OrcaSlicer |
|-|--------------|---------------------|
| Install folder | `C:\Program Files\Cosmyx\CosmoSlice` | `C:\Program Files\OrcaSlicer` |
| Uninstall key | `...\CurrentVersion\Uninstall\Cosmyx CosmoSlice` | `...\CurrentVersion\Uninstall\OrcaSlicer` |
| Publisher | `Cosmyx` | `SoftFever` |
| Apps & features name, installer title | `CosmoSlice` | `OrcaSlicer` |
| Start menu folder | `Cosmyx\CosmoSlice` | `OrcaSlicer` |
| Executable | `orca-slicer.exe` | `orca-slicer.exe` |

The values are set in `cmake/cosmyx/Packaging.cmake`. The executable name, the
Start menu shortcut label and the remaining product-name texts belong to the
product-name branding (`cosmyx-src/branding/product-name/`).

### Upgrades and earlier installs

- An earlier install of the same Cosmyx build (key `Cosmyx CosmoSlice`): the
  installer offers to uninstall it first (CPack's uninstall-before-install).
- An earlier CosmoSlice build (key `Cosmyx OrcaSlicer`, publisher `Cosmyx`,
  folder `Program Files\Cosmyx\OrcaSlicer`): removed silently before the files
  are copied (`cmake/cosmyx/remove_legacy_install.nsh`).
- A Cosmyx build made on the upstream values (key `OrcaSlicer`, publisher
  `SoftFever`): left in place, since it cannot be told apart from upstream
  OrcaSlicer. Uninstall it by hand from Apps & features if needed.
- Upstream OrcaSlicer: never touched.

## Shared with upstream OrcaSlicer

These still carry the upstream names, so the two apps share them:

- the file association ProgID (`Orca.Slicer.1` under `HKCU\Software\Classes`):
  the app that registered last opens `.3mf`, `.stl` and the other model files;
- the single-instance D-Bus names on Linux;
- the macOS bundle id and the Flatpak app id, and with it the Flatpak sandbox
  folder (the `Cosmyx` folder keeps the data apart inside it).

## Where it is implemented

- `src/libslic3r/Cosmyx/DataDir.{hpp,cpp}`: the vendor name and the path
  helpers (tests: `tests/cosmyx/test_cosmyx_paths.cpp`).
- `src/slic3r/GUI/Cosmyx/AppPaths.{hpp,cpp}`: the wxWidgets vendor setting.
- `cmake/cosmyx/Packaging.cmake` and `cmake/cosmyx/remove_legacy_install.nsh`:
  the installer (tests: `scripts/cosmyx/tests/test_install_paths.py`, run by
  `just test-scripts`).
- The upstream hook lines are listed in decisions 0181 and 0185.
