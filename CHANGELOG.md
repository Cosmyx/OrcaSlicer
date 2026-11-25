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
- Show the version as `<OrcaSlicer version>-<Cosmyx patch>` (for example
  `2.6.0-8`, or `2.6.0-dev-8` on a development base; the patch starts at 8)
  in the About dialog, the splash screen, the network test and the
  troubleshoot dialogs, and name CI builds and artifacts
  `<that version>_<short commit hash>`. Pull request: pending.
  Decisions: 0060, 0061, 0062, 0063, 0064.

<!-- cosmyx-slot: T7 -->

<!-- cosmyx-slot: T11b -->

<!-- cosmyx-slot: T11c -->

<!-- cosmyx-slot: T11d -->

<!-- cosmyx-slot: T11e -->

<!-- cosmyx-slot: T11f -->

<!-- cosmyx-slot: T26 -->
- The update check (at startup and from Help > Check for Updates) now looks
  for releases of the Cosmyx fork on GitHub instead of OrcaSlicer's, and only
  ever offers a published release (never a draft, pre-release, dev or nightly
  build), tagged `v<OrcaSlicer base>.<Cosmyx patch>` (for example `v2.5.2.8`)
  and shown as `2.5.2-8`. It never goes online in Stealth mode: the menu
  command then says so. The "Check for stable updates only" box is gone from
  the update popup. "Publish to draft release" now publishes the CosmoSlice
  files of a Build all run, refuses a tag outside that convention or a build
  of another version, and creates the draft on the run's commit when it is
  missing (the `RELEASE_PUBLISHER` repository variable must name who may run
  it). The Stealth mode message is translated into French and
  machine-translated for review into the 20 other offered UI languages.
  Pull request: https://github.com/Cosmyx/OrcaSlicer/pull/122.
  Decision: 0221.

### i18n

<!-- cosmyx-slot: T8 -->

### CI-release

<!-- cosmyx-slot: T9 -->

<!-- cosmyx-slot: T10 -->

<!-- cosmyx-slot: T11a -->

<!-- cosmyx-slot: T13 -->
