# 0183. Remove an earlier Cosmyx install only when it is positively Cosmyx

## Status

Accepted.

## Context

With a new install folder and uninstall key (decision 0182), an earlier Cosmyx
install would stay next to the new one. It may only be removed when it is
certainly a Cosmyx build: an upstream OrcaSlicer install must never be
touched.

Known earlier Windows installs:

- CosmoSlice builds: key `Cosmyx OrcaSlicer`, publisher `Cosmyx`, folder
  `Program Files\Cosmyx\OrcaSlicer`. Identifiable.
- Cosmyx builds made on the upstream values: key `OrcaSlicer`, publisher
  `SoftFever`, folder `Program Files\OrcaSlicer`. Identical to upstream, so
  they cannot be told apart.

## Decision

- `cmake/cosmyx/remove_legacy_install.nsh` runs before the files are copied.
  For each listed legacy key, in `HKLM` and `HKCU`, it removes the install
  only when the key's `Publisher` is exactly `Cosmyx`: it runs the registered
  `Uninstall.exe` silently in place, then deletes it and the folder if empty.
- The only listed key is `Cosmyx OrcaSlicer`. The upstream key `OrcaSlicer` is
  never listed; the current key is handled by CPack's own
  uninstall-before-install step.
- Cosmyx builds made on the upstream values are not removed; users uninstall
  them by hand if they want to.

## Consequences

- Upgrading from a CosmoSlice build leaves one Cosmyx install; upgrading from
  an upstream-valued Cosmyx build leaves both, as does having upstream
  OrcaSlicer installed.
- `scripts/cosmyx/tests/test_install_paths.py` pins the rule: no listed key is
  the upstream or current key, the publisher check comes before any step that
  runs or deletes anything, and no registry key or folder tree is deleted
  directly.
- Removing it: delete the `.nsh` file and its append in `Packaging.cmake`.
