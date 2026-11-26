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
- A bed temperature of -1 turns the bed heater off: the G-code writes
  `M140 S0` and never waits with `M190`, and the bed temperature placeholders
  read 0. A value of 0 still means the filament does not support the plate.
  Pull request: pending. Decisions: 0010, 0011, 0012.

<!-- cosmyx-slot: T2 -->
- Add the CHT nozzle type (HRC 65) to the printer nozzle type choices,
  next to the upstream types, tungsten carbide included. Pull request: pending.
  Decisions: 0020, 0021, 0022.

<!-- cosmyx-slot: T3 -->
- Add a per-filament ironing temperature (Filament > Print temperature): the
  nozzle switches to it while ironing and goes back to the print temperature
  afterwards, including for a tool left after ironing on multi-tool printers.
  0, the default, changes nothing. Values outside 0 to 500 are refused when
  the configuration is checked before slicing, like any other out of range
  setting. Pull request: pending. Decisions: 0030, 0031, 0032, 0033, 0034,
  0035, 0036.

<!-- cosmyx-slot: T4 -->
- Fix the order of a tool change and its fan commands: the new tool's part
  cooling fan speed, and the fan resume that follows a change G-code, are now
  written after its `Tn`, so printers with one fan per tool drive the right
  fan. Pull request: #91. Decisions: 0040.

### GUI

<!-- cosmyx-slot: T5 -->

<!-- cosmyx-slot: T6 -->

<!-- cosmyx-slot: T7 -->

<!-- cosmyx-slot: T11b -->

<!-- cosmyx-slot: T11c -->

<!-- cosmyx-slot: T11d -->

<!-- cosmyx-slot: T11e -->

<!-- cosmyx-slot: T11f -->

<!-- cosmyx-slot: T28 -->
- The GUI now knows whether the selected printer is a Cosmyx machine: its
  preset, or the system preset it inherits from, belongs to the Cosmyx
  printer bundle (vendor id `Cosmyx`). A custom printer with no system parent
  is not one. Cosmyx-only features use this flag and follow it each time the
  printer changes, the first preset load at startup included. Nothing visible
  changes by itself. Pull request: https://github.com/Cosmyx/OrcaSlicer/pull/125.
  Decision: 0222.

### i18n

<!-- cosmyx-slot: T8 -->

### CI-release

<!-- cosmyx-slot: T9 -->

<!-- cosmyx-slot: T10 -->
- Add the scheduled upstream sync: every two hours `Orca-Upstream` mirrors
  upstream `main`, `MIXED` is rebuilt as `DEV` merged with it (a conflict fails
  the run and lists the files), `build_all` runs on `MIXED` when it moved, and
  the upstream bots are kept disabled by a scheduled workflow policy. Needs the
  `UPSTREAM_SYNC_TOKEN` secret. Pull request: https://github.com/Cosmyx/OrcaSlicer/pull/87. Cosmyx-owned
  `cosmyx-*.yml` workflows may be scheduled without a policy entry. Decisions:
  0100, 0101, 0102, 0103, 0104, 0105.

<!-- cosmyx-slot: T11a -->

<!-- cosmyx-slot: T13 -->
