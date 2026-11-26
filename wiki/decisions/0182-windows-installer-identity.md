# 0182. Windows installer identity: Program Files\Cosmyx\CosmoSlice

## Status

Accepted.

## Context

Upstream's NSIS installer installs to `Program Files\OrcaSlicer`, registers
the uninstall key `OrcaSlicer` with the publisher `SoftFever`, and with
`CPACK_NSIS_ENABLE_UNINSTALL_BEFORE_INSTALL` offers to remove whatever is
registered under that key. A Cosmyx installer with the same values would
replace an upstream install, and the other way round. The product-name
branding (decision 0132) appends `CPACK_NSIS_DISPLAY_NAME "CosmoSlice"` at
build time, and left the install folder and registry key named OrcaSlicer.

## Decision

- `cmake/cosmyx/Packaging.cmake`, included right before `include(CPack)`,
  overrides:
  - `CPACK_PACKAGE_VENDOR` = `Cosmyx` (the publisher in Apps & features, and
    the `Software\Cosmyx` registry folder);
  - `CPACK_PACKAGE_INSTALL_DIRECTORY` = `Cosmyx\CosmoSlice` (also the default
    Start menu folder);
  - `CPACK_PACKAGE_INSTALL_REGISTRY_KEY` = `Cosmyx CosmoSlice`;
  - `CPACK_NSIS_DISPLAY_NAME` and `CPACK_NSIS_PACKAGE_NAME` = `CosmoSlice`, only
    when not already defined. Both default to the install directory, which
    would show `Cosmyx\CosmoSlice`.
  - `CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS`: appends the legacy-install removal
    (decision 0183) after upstream's signing include, never replacing it.
- Split with the product-name branding: this file owns the folder, key,
  vendor and the installer window title; the branding's appended
  `CPACK_NSIS_DISPLAY_NAME` comes first and is kept by the guard, so both
  agree on `CosmoSlice` and nothing is defined twice in effect. The Start menu
  shortcut label (`CPACK_PACKAGE_EXECUTABLES`) stays with the branding.
- `CPACK_PACKAGE_NAME` and the executable name stay `OrcaSlicer` /
  `orca-slicer.exe` (decision 0132).

## Consequences

- A Cosmyx install and an upstream OrcaSlicer install live side by side, each
  with its own folder, uninstall entry and uninstall-before-install check.
- Both still register the same file association ProgID, so the last one
  started owns `.3mf` / `.stl`.
- Removing it: delete the hook line and `cmake/cosmyx/`; the installer is
  upstream's again.
