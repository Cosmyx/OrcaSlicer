# 0132. The product name is CosmoSlice at build time, the app key stays

## Status

Accepted.

## Context

The Cosmyx build must show the name CosmoSlice, while the git tree stays
OrcaSlicer (zero conflict with upstream) and existing installs keep working:
their data folder, registry entries, file associations and update channel
are all keyed by the name OrcaSlicer.

## Decision

- The branding engine renames the product while it brands the tree, from
  `cosmyx-src/branding/product-name/patches.json` (exact, counted text
  patches) and `rename.json` (decision 0134). Nothing is committed in an
  upstream file.
- Renamed (visible): `SLIC3R_APP_NAME` in `version.inc` (so every
  `@SLIC3R_APP_NAME@` resource, the window titles and the About box follow),
  `SLIC3R_APP_FULL_NAME` and `GCODEVIEWER_APP_NAME` in `libslic3r.h` (now
  built on `SLIC3R_APP_NAME`), the wx display name (`SetAppDisplayName`,
  commented out upstream), the macOS menu bar name (`MACOSX_BUNDLE_BUNDLE_NAME`),
  the installer summary and Apps & features name (`CPACK_NSIS_DISPLAY_NAME`
  appended), the MSIX package and Start menu display names, the AppImage,
  Linux and Flatpak menu names, the TLS question title, the dock tooltip, the
  setup wizard and login window titles, the built-in action source name, the
  desktop entries the Linux desktop integration writes, the default title of
  plugin windows, and the setup guide's fallback text.
- Kept (`SLIC3R_APP_KEY` and everything named after it): the data folder
  (`SetAppName(SLIC3R_APP_KEY)`), the `.app`, `.exe` and AppImage names, the
  bundle and Flatpak ids, the MSIX identity, ProgID and AppData exclusion, the
  registry key and install folder (`CPACK_PACKAGE_NAME`,
  `CPACK_PACKAGE_INSTALL_REGISTRY_KEY`), icon and desktop file names, and the
  `OrcaSlicer_` artifact prefix (the artifact checks rely on it).
- Beyond the plan's list, the residue scan found more visible names, patched
  the same way, one counted row each: the MSIX package display name, the
  wizard and login titles, the action source name, the plugin window title
  and the desktop integration entry names.
- `resources/data/hints.ini` is renamed by the rename table, not by patches:
  a hint is a msgid, so the hint and its catalogue entries change together.
  `resources/web/data/text.js` no longer exists upstream (the guide strings
  are msgids now); no row targets it.

## Consequences

- A build shows CosmoSlice everywhere a user reads the name, and an existing
  OrcaSlicer configuration, project or file association keeps working.
- Left for later, not renamed: the installer window title and the Start menu
  shortcut label (`CPACK_NSIS_PACKAGE_NAME`, `CPACK_PACKAGE_EXECUTABLES`), and
  the Flatpak description paragraphs.
- Removing it: delete `cosmyx-src/branding/product-name/` and
  `scripts/cosmyx/branding/product_name/`; the build is OrcaSlicer again.
