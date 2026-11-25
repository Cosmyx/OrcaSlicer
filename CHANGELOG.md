# Changelog

Changes made in the Cosmyx fork of OrcaSlicer. Upstream changes are not listed
here; see the upstream release notes.

## Rules

- Every change records one line here, in its own branch, in the same pull
  request. A branch without its line is not finished.
- Newest first: periods are months (`## YYYY-MM`), the current one at the top.
  Open a new period when the first change of a month lands.
- Inside a period, lines are grouped by area, always in this order:
  `repo` (tooling, layout, docs), `libslic3r` (slicing core), `GUI`,
  `i18n` (translations), `CI-release` (workflows, signing, releases).
- Each line says what changed for someone reading the history, not how. It
  ends with the pull request link and the decisions it implements
  (`wiki/decisions/NNNN-slug.md`).
- Breaking changes, removals and migrations start with **Breaking:**,
  **Removed:** or **Migration:** and say what the reader has to do.
- Slot markers (`<!-- cosmyx-slot: Tn -->`) reserve a place for each planned
  task, so parallel branches never edit the same lines. A task inserts its line
  directly under its own marker and never removes or moves a marker.

## 2026-11

### repo

<!-- cosmyx-slot: T0 -->
- Add the Cosmyx foundation: the libslic3r and GUI Cosmyx modules with their
  one-line upstream hooks, the cosmyx_tests suite, this changelog, the decision
  register under `wiki/decisions/`, the justfile and the Cosmyx checks
  workflow. Pull request: https://github.com/Cosmyx/OrcaSlicer/pull/86. Decisions: 0001, 0002, 0003, 0004.

### libslic3r

<!-- cosmyx-slot: T1 -->

<!-- cosmyx-slot: T2 -->

<!-- cosmyx-slot: T3 -->

<!-- cosmyx-slot: T4 -->

### GUI

<!-- cosmyx-slot: T5 -->

<!-- cosmyx-slot: T6 -->

<!-- cosmyx-slot: T7 -->

<!-- cosmyx-slot: T11b -->

<!-- cosmyx-slot: T11c -->
- Turn the Orca teal into the Cosmyx violets at build time: 24 colour
  mappings (all validated by the user on 2026-11-19, with their WCAG contrast
  on white and on the dark screen), 115 exact literal rows for numeric colours,
  the dark grey `#242323` as default filament colour instead of the teal
  (accents stay violet), one dark-mode snippet for the CSS-form SVG icons,
  and a guard that fails on any teal left unless allow-listed. URL fragments and numeric character references are never
  taken for colours, and palette values must be uppercase `#RRGGBB`. On an
  older upstream base (tolerant mode, decision 0122) literal rows whose file
  or text that tree lacks are skipped with a warning.
  Recipes `just brand-colour-candidates` and
  `brand-colour-literals`. Pull request: pending. Decisions: 0127, 0128,
  0129, 0130.

<!-- cosmyx-slot: T11d -->

<!-- cosmyx-slot: T11e -->

<!-- cosmyx-slot: T11f -->

### i18n

<!-- cosmyx-slot: T8 -->
- Translate the Cosmyx strings: per-feature catalogues under
  `localization/cosmyx/` (cht-nozzle, ironing-temperature, models) for every
  OrcaSlicer language, seeded from the previous Cosmyx branch, grafted into
  the OrcaSlicer catalogues by every desktop build, Flatpak included (its
  container workspace is trusted for git), without marking the build "-dirty"
  (the edited files are hidden from git diff).
  Recipes `just i18n-extract`, `i18n-seed`, `i18n-graft`, `i18n-ungraft`,
  `worktree-hidden`. The graft accepts UTF-8 catalogues only, reads strings
  holding Unicode line separators, and never glues an entry to a catalogue
  without a final newline. Pull request: pending. Decisions: 0080, 0081, 0082
  (superseded), 0083, 0084, 0085, 0086, 0087, 0088.

### CI-release

<!-- cosmyx-slot: T9 -->

<!-- cosmyx-slot: T10 -->

<!-- cosmyx-slot: T11a -->
- Apply the Cosmyx branding at build time from tables under
  `cosmyx-src/branding/` (image manifest of 560 rows, all missing for now,
  and the vendored overlay), with guards before and after, an exact revert,
  and a clean git tree. Unvalidated rows warn on development builds and fail
  release builds. Malformed tables, symlinks, case-only path differences and
  failing stages are refused and reverted with a report, and an interrupted
  revert can be resumed. Recipes `just brand-check`, `brand-apply`, `brand-revert`,
  `brand-sync`, `brand-refresh`, `brand-validate` (user only), `brand-table`;
  workflow in `wiki/cosmyx/branding.md`. Pull request: pending. Decisions:
  0120, 0121, 0122, 0123.

<!-- cosmyx-slot: T13 -->
