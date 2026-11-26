# 0123. The image manifest is discovered from the tree

## Status

Accepted.

## Context

About 520 upstream SVG icons carry the Orca teal and about 36 files are
branding images (application icons, splash, About banner, MSIX tiles). The
list changes with upstream, and a hand-written list would go stale.

## Decision

- `just brand-sync` discovers the rows:
  - every SVG under `resources/images` and `resources/web` holding a colour of
    the teal family (HSL hue 160-190, saturation at least 0.25, lightness at
    least 0.15, `#00AE42` and `#1F8EEA` excluded), with the hex rule of the
    frozen contract (`#RRGGBB` in any case, not followed by a hex digit, never
    in an `href`, a `url(...)`, a URL fragment, a numeric character reference
    `&#NNNNNN;` or base64 data);
  - every branding image matching the name patterns of `manifest.py`
    (`resources/images/OrcaSlicer*`, `splash_logo*`, `studio_logo*`,
    `stl.icns`, `gcode.icns`, `resources/Icon.icns`,
    `resources/web/image/logo*`, `scripts/msix/assets/*`);
  - every overlay file.
- Groups: `logos` for the branding images, `web` for resources/web,
  `icons-a-m` and `icons-n-z` for resources/images split on the first letter
  below that folder. A row never moves group.
- Sync adds `missing` rows, drops a row without a replacement once its file is
  gone or no longer teal, refreshes the hash and size of rows without a
  replacement, records a new overlay file as `to-validate` (source `user`),
  and never touches a row with a replacement: that is `brand-refresh`'s job.
- Hashes are SHA-256 over LF bytes for SVG and raw bytes otherwise. Each
  table is `{"schema": 1, "group", "rows"}`, rows sorted by path with the
  fields in the frozen order, two-space JSON with a final newline. Paths are
  relative POSIX paths; absolute paths, backslashes, `.` and `..` are
  rejected.
- `just brand-table` writes the review tables
  `wiki/cosmyx/branding-assets/<group>.md` from the manifest only, so they are
  deterministic; guard G6 fails when they are stale.
- `usage` is free text for the reviewer; sync keeps it as written.

## Consequences

- An upstream icon or logo variant gets its row on the next sync, and G4
  reports it until then.
- Removing it: the tables become hand-written and G4 has nothing to compare
  against.
