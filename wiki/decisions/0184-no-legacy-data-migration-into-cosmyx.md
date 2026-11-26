# 0184. The Cosmyx data folder is never the target of a legacy data migration

## Status

Accepted. Amends 0180 and 0181.

## Context

Decision 0180 records the user's choice: a Cosmyx build keeps its data in
`Cosmyx/OrcaSlicer` on every OS and starts fresh, with no migration.

Upstream has one legacy data folder migration: on Linux, inside a Flatpak,
`migrate_flatpak_legacy_datadir()` (`GUI_App.cpp`) copies
`~/.var/app/io.github.softfever.OrcaSlicer/config/OrcaSlicer` into the data
folder when the data folder does not exist yet. The first version of the
0181 hook rewrote the legacy path with the vendor folder taken out, so a
Cosmyx Flatpak copied upstream's legacy data into `Cosmyx/OrcaSlicer`,
against 0180. Left untouched, upstream's code would look for
`.../io.github.softfever.OrcaSlicer/config/Cosmyx/OrcaSlicer`, which is
unlikely to exist but is not guaranteed not to.

No other upstream code copies a legacy data folder: Windows and macOS take
the data folder from `wxStandardPaths::GetUserDataDir()` and only create it;
`check_old_linux_datadir()` only compares paths; the preset migration on
login works inside the data folder.

## Decision

- `Cosmyx::skip_legacy_data_migration(data_dir)`
  (`src/libslic3r/Cosmyx/DataDir.*`) is true when the data folder sits right
  under the `Cosmyx` vendor folder.
- `migrate_flatpak_legacy_datadir()` gets one inserted line right after its
  "not running as a Flatpak" return: it returns early when that predicate is
  true. The upstream legacy path line is back to upstream's text, so the hook
  is a pure insertion.
- A custom `--datadir` never reaches the migration (upstream only calls it for
  the default folder); a portable `data_dir` folder is not nested under
  `Cosmyx`, so it keeps upstream behaviour.
- `Cosmyx::without_vendor_dir()` is removed: it only served the old hook.

## Consequences

- A Cosmyx Flatpak starts with an empty `Cosmyx/OrcaSlicer` folder even when
  upstream's legacy Flatpak data exists.
- Tests: `tests/cosmyx/test_cosmyx_paths.cpp` checks the predicate;
  `scripts/cosmyx/tests/test_install_paths.py` pins the hook line and its
  place.
- Removing it: delete the inserted line in `migrate_flatpak_legacy_datadir()`
  and the predicate with its tests; the Flatpak would then look for upstream's
  legacy data under `.../io.github.softfever.OrcaSlicer/config/Cosmyx/OrcaSlicer`.
