# 0122. Guards G1-G8 and their severity

## Status

Accepted.

## Context

The branding edits hundreds of files the tables describe by hash and by
count. Upstream changes those files on its own schedule, and `MIXED` (DEV
merged with upstream) must keep building to show merge problems.

## Decision

- `scripts/cosmyx/branding/guards.py` runs before (`pre`) and after (`post`)
  apply: G1 overlay hash, G2 no orphan overlay, G3 upstream file and hash,
  G4 every teal SVG and branding image has a row, G5 colour literal counts and
  teal residue, G6 tables valid, canonical and rendered, G7 no palette colour
  or "CosmoSlice" in tracked upstream-owned files, G8 product-name patch
  counts and unchanged `SLIC3R_APP_KEY` lines.
- Drift, an upstream change the tables have not caught up with (G3, G4),
  follows the status policy of decision 0121: a warning on development
  builds, an error on release builds. `just brand-sync` or
  `just brand-refresh` catches up. Every other finding is an error on every
  build.
- G5 reads `scopes` from colours.json as fnmatch globs on repository paths,
  `!` marking an exclusion. The teal family and the ignored colours come from
  its `family` and `ignore`, with the frozen defaults until it exists.
- `allow_residue` rows of colours.json permit an exact count of a colour in a
  file, both for the G5 residue and for the G7 palette check: upstream itself
  contains `#8000FF` (for example a colour picker palette), which needs such a
  row once the palette exists.
- G7 uses `git grep` on tracked files and skips with a warning outside a git
  checkout. Cosmyx paths (`cosmyx-src/`, `scripts/cosmyx/`, `wiki/`,
  `src/*/Cosmyx/`, `localization/cosmyx/`, names containing `cosmyx`, the
  changelog and the justfile) are exempt.
- G5 and G8 are inactive until their tables exist, and call the guards of the
  colour and product-name plugins when those exist.

## Consequences

- A new upstream icon never breaks `MIXED` or a pull request, but blocks a
  release until it is synced and validated.
- Removing a guard: delete its function from `GUARDS` and its tests.
