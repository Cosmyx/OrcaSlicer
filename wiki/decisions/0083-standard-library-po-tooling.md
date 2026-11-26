# 0083. Standard library PO tooling

## Status

Accepted.

## Context

The graft runs on every build leg: Linux, macOS and Windows runners. The
gettext tools are missing from the Windows and Linux runner images, and polib
would need a pip install on each leg. The build steps after the graft rely on
the runner's own Python.

## Decision

- `scripts/cosmyx/i18n_graft.py` reads and writes PO files with the Python
  standard library only. Untouched entries are written back byte for byte, so
  a graft changes only the grafted entries; a test round-trips the real French
  catalogue.
- The composite action installs Python 3.12 with `actions/setup-python@v7`
  (the version upstream workflows pin) and `update-environment: false`, and
  calls that interpreter by path, so the rest of the build keeps the runner's
  Python on PATH.
- `scripts/cosmyx/i18n_extract.py` reuses the same reader and writer.

## Consequences

- No third-party dependency and no package install on the build legs.
- The reader is a few hundred lines to maintain; its tests cover escapes,
  plurals, contexts, obsolete entries and malformed input.
- Removing it: replace the reader with polib or with
  `msgattrib --no-obsolete | msgcat --use-first`, which needs gettext on every
  leg.
