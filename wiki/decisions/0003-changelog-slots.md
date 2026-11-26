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

- A task split into sub-tasks gets one marker per sub-task, with a lower-case
  letter suffix (`<!-- cosmyx-slot: T11a -->`).
- Markers in place, by area:
  - `repo`: T0, T17, T20.
  - `libslic3r`: T1, T2, T3, T4, T12.
  - `GUI`: T5, T6, T7, T11b, T11c, T11d, T11e, T11f, T28, T26, T16, T18, T24, T11g.
  - `i18n`: T8.
  - `CI-release`: T9, T10, T11a, T13, T15, T16a, T19, T22.
- Decision numbers are reserved in ranges per task so parallel branches never
  take the same number: T11 uses 0120-0139, T12 uses 0110-0119, T13 uses
  0140-0149, T15 uses 0150-0159.

## Consequences

- Markers stay in the file after their task merges; they cost nothing in the
  rendered page.
- A new task gets its marker added by the change that plans it.
