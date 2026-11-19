# 0003. Changelog slot markers

## Status

Accepted.

## Context

Every change records a line in `CHANGELOG.md`. Branches developed in parallel
would all insert at the top of the same section and conflict with each other.

## Decision

- `CHANGELOG.md` has its rules at the top, one current period (a month), and
  fixed areas in a fixed order: `repo`, `libslic3r`, `GUI`, `i18n`,
  `CI-release`.
- Under each area, one HTML comment marker per planned task,
  `<!-- cosmyx-slot: Tn -->`, separated by blank lines.
- A task inserts its line directly under its own marker and never removes or
  moves a marker, so two branches never touch the same lines.

## Consequences

- Markers stay in the file after their task merges; they cost nothing in the
  rendered page.
- A new task gets its marker added by the change that plans it.
