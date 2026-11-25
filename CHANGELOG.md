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
- Ship the CosmoSlice application icon, About dialog logos and splash
  screen in Cosmyx builds: 11 files vendored from CosmoSlice (window,
  taskbar and Linux desktop icons, About banner, splash) and 6 rasters
  derived from the CosmoSlice SVG master by `just brand-derive` in a pinned
  resvg image (multi-size Windows icon, macOS app icon, MSIX tiles). The
  other logos (file-type icons, bed texture, web and dialog logos) keep the
  Orca files for now. Pull request: #101. Decisions: 0124, 0125, 0126.
- Ship the remaining CosmoSlice logos in Cosmyx builds: 11 files vendored
  from CosmoSlice (bed texture, gradient and gray logos, configuration
  wizard and unreferenced logos) and 6 rasters derived from the SVG master
  (macOS document, G-code and STL file-type icons, grayscale message logo,
  title logo, web header logo). The horizontal Troubleshoot logos and
  `web/image/logo2.png` are still missing. Pull request: #130.
  Decisions: 0124, 0125.

<!-- cosmyx-slot: T11c -->

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
  revert can be resumed. Builds of a tree whose upstream base is not DEV
  (integrations onto older upstream tags) brand in tolerant mode: a row whose
  target file or text that tree lacks is skipped with a warning; DEV and
  release builds stay strict (`just brand-mode`, `brand-apply tolerant`). Recipes `just brand-check`, `brand-apply`, `brand-revert`,
  `brand-sync`, `brand-refresh`, `brand-validate` (user only), `brand-table`;
  workflow in `wiki/cosmyx/branding.md`. Pull request: pending. Decisions:
  0120, 0121, 0122, 0123.

<!-- cosmyx-slot: T13 -->
