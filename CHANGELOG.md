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
  `resources/cosmyx` and `resources/info` folders the suite reads), this
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

<!-- cosmyx-slot: T28 -->
- The GUI now knows whether the selected printer is a Cosmyx machine: its
  preset, or the system preset it inherits from, belongs to the Cosmyx
  printer bundle (vendor id `Cosmyx`). A custom printer with no system parent
  is not one. Cosmyx-only features use this flag and follow it each time the
  printer changes, the first preset load at startup included. Nothing visible
  changes by itself. Pull request: https://github.com/Cosmyx/OrcaSlicer/pull/125.
  Decision: 0222.

<!-- cosmyx-slot: T31 -->
- On a Cosmyx printer, the "Connection" button of the printer title bar opens
  a Cosmyx physical printer dialog instead of the generic one. Its "Setup" tab
  asks only for the preset name, the machine IP (or host name, with an
  optional port) and the API key, saves the OctoPrint address, the machine web
  interface and the key into the printer preset, and tests the connection.
  Its "Machine information" tab, enabled once the settings are saved and a
  connection test succeeded (one runs by itself when the dialog opens on a
  configured machine), reads the model, serial number, versions, installed
  options, hot ends and camera from the machine. Other printers keep the
  generic dialog. The dialog is translated into French and machine-translated
  for review into the 20 other offered UI languages. Pull request:
  https://github.com/Cosmyx/OrcaSlicer/pull/127.
  Decision: 0225.

### i18n

<!-- cosmyx-slot: T8 -->

### CI-release

<!-- cosmyx-slot: T9 -->

<!-- cosmyx-slot: T10 -->

<!-- cosmyx-slot: T11a -->

<!-- cosmyx-slot: T13 -->
