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
- Stealth mode is always on: no cloud login, profile sync or online vendor
  update, whatever the Preferences or the login dialog say, and the setup
  guide finishes without the stealth mode and network plugin pages. Pull
  request: pending. Decisions: 0070, 0071, 0072, 0073.

<!-- cosmyx-slot: T11b -->

<!-- cosmyx-slot: T11c -->

<!-- cosmyx-slot: T11d -->

<!-- cosmyx-slot: T11e -->

<!-- cosmyx-slot: T11f -->

<!-- cosmyx-slot: T18 -->
- Cosmyx now uses its own cloud, CosmoCloud (orca-cloud.cosmyx3d.fr), for
  sign-in, sync and the plugin hub, and stealth mode can be turned off again:
  it is on by default until the user opts out. Preferences can point the app
  at a custom cloud instance ("Custom Cloud Instance", translated into
  French and machine-translated for review into the 20 other offered UI
  languages; British English keeps the source text), over https or over plain
  http on the local machine (localhost) for testing; cloud addresses set by
  the user always win.
  Pull request: pending. Decisions: 0200, 0201, 0202, 0203.
- **Breaking:** cloud plugins are installed and updated only when their
  CosmoCloud package signature verifies, and never as an older version than
  the one installed. The production signing key is not pinned yet, so plugins
  from the Cosmyx cloud cannot be installed until a release adds it; installed
  plugins keep working. A custom cloud instance needs its signing key pinned
  in Preferences, or the user's explicit choice to allow unverified plugins
  from it; these settings belong to one server address. Plugins are refused
  from a cloud address that is not a plain `https://host[:port][/path]`
  (plain http only on the local machine), and Preferences no longer accepts
  such addresses: plain http on the local machine now needs `localhost`,
  `[::1]` or `127.x.x.x` without leading zeros. A package swapped during its
  install, or whose entry package could escape the plugin folder, is refused,
  and so is a plugin download that ends after the app was closed. The
  plugin signing settings and messages are translated into French.
  Pull request: https://github.com/Cosmyx/OrcaSlicer/pull/112. Decision: 0204.

### i18n

<!-- cosmyx-slot: T8 -->

### CI-release

<!-- cosmyx-slot: T9 -->

<!-- cosmyx-slot: T10 -->

<!-- cosmyx-slot: T11a -->

<!-- cosmyx-slot: T13 -->
