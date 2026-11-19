# 0005. Flatpak test asset keeps the Cosmyx resources

## Status

Accepted.

## Context

The flatpak build leg packs a slimmed build tree as the unit test asset. Its
"Package flatpak test asset" step in `.github/workflows/build_flatpak.yml`
deletes every folder under `resources/` except `profiles`, `printers` and
`images`. `cosmyx_tests` also reads `resources/cosmyx` (Cosmyx model files)
and `resources/info` (`nozzle_info.json`, the nozzle hardness table), so its
cases failed in the flatpak leg only, where those folders were missing.

## Decision

- The `find "$d/resources" ...` filter of that step also keeps `cosmyx` and
  `info`: `! -name cosmyx ! -name info`, with a `# Cosmyx:` comment line above
  it. It is an upstream hook in the sense of decision 0002: one edited line
  plus its comment.
- The unpack and run steps (`unit_tests_flatpak.yml`) need no change: they
  extract the whole tar and run ctest from the build tree.
- `scripts/cosmyx/tests/test_foundation.py` pins the filter, so a rewrite of
  the step that drops either folder fails `just test-scripts`.

## Consequences

- The asset grows by the size of those two folders (a few hundred kilobytes).
- Removing the hook means deleting `! -name cosmyx ! -name info` and the
  comment line, and the Cosmyx cases that read those folders then fail in the
  flatpak leg.
