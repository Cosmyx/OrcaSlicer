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
  one-line upstream hooks, the cosmyx_tests suite (built and run by every
  test leg, the flatpak one included, whose test asset keeps the
  `resources/cosmyx` and `resources/info` folders the suite reads, checked
  in whichever workflow file the upstream base keeps that job), this
  changelog, the decision register under `wiki/decisions/`, the justfile and
  the Cosmyx checks workflow. Pull request: https://github.com/Cosmyx/OrcaSlicer/pull/86. Decisions: 0001, 0002, 0003, 0004, 0005.

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

<!-- cosmyx-slot: T11d -->

<!-- cosmyx-slot: T11e -->

<!-- cosmyx-slot: T11f -->

### i18n

<!-- cosmyx-slot: T8 -->

### CI-release

<!-- cosmyx-slot: T9 -->

<!-- cosmyx-slot: T10 -->

<!-- cosmyx-slot: T11a -->

<!-- cosmyx-slot: T13 -->
- Check every "Build all" run's artifacts on their own OS: Windows signatures
  and installer payload, macOS architectures and arm64 signatures, Linux ELF
  files with a smoke run and a slice, plus the build tag in the names and the
  shipped translations and models. Posts the commit status
  `cosmyx/artifact-checks`; signatures are enforced only on signed builds (see
  `wiki/cosmyx/artifact-checks.md`). Pull request: pending. Decisions: 0140,
  0141, 0142, 0143, 0144, 0145, 0146, 0147, 0148, 0149.
