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

<!-- cosmyx-slot: T20 -->
- `just cosmo-integrate` and `just cosmo-rebase-check` take `--bundle N` to
  build one Cosmyx bundle: every branch of the integration list now has a
  `bundle` (8 for the bundle-7 features rebased on OrcaSlicer 2.5.2 and the
  integration and build tooling, 9 for the new features), and only the
  branches of bundle N or earlier are kept; without the option every branch
  is kept as before. A branch whose parent is in a later bundle is refused.
  Pull request: https://github.com/Cosmyx/OrcaSlicer/pull/115. Decisions: 0226.
- Add `just cosmo-integrate [BASE]`, which rebuilds a throwaway integration
  branch (`ci/cosmyx-integration` on DEV, `integration/<BASE>` on any other
  base, so both coexist) from every Cosmyx pull request branch (on a base
  other than DEV, each branch's own commits are first replayed onto it as
  `rebase/<BASE>/<branch>`, so DEV's newer commits are not dragged in) and
  resolves the known conflicts (changelog slots, slot lists, branding tables,
  recorded resolutions) inside the merge commits, stopping on any other one,
  and `just cosmo-rebase-check TAG`, a dry run that replays every branch onto
  an upstream tag and prints a conflict table. `--push --build` builds the
  integration through a never-merged draft pull request into
  `cosmyx-ci/<BASE>`, a branch pushed at the base commit, which the Cosmyx
  dev build workflow builds; `--os LIST` picks its OSes through the pull
  request's `build:*` labels. On a base other than DEV, a resolution that
  copies a replayed commit's whole file is refused (`--allow-whole-copy PATH`
  accepts one), and upstream files changed by more than `--drift-threshold`
  lines are listed in a drift warning (`--strict-drift` stops the run). The
  branch list and
  order live in `scripts/cosmyx/integrate/branches.json`. Pull request:
  https://github.com/Cosmyx/OrcaSlicer/pull/115.
  Decisions: 0215.

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
