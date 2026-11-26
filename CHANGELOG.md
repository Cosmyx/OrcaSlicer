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
- Add the "Cosmyx 3D Models" menu to the empty-space and plate context menus:
  Dual Head calibration models (Calage 1, 2 and 3 SNDT, Cube Bicolore), Single
  Head ones (Calage 1 Nova, Cosmyx Cube) and handy models (belt tension
  control, spool holder). Calage 1 offers 0 degree infill directions; Calage 3
  offers its base settings and adds its modifier boxes to the loaded objects
  only. The menu icon uses the grey and violet of its sibling menu icons.
  The menu is shown only while the selected printer is a Cosmyx machine: it
  disappears when another printer is selected and comes back right after "Add
  Handy models" when a Cosmyx printer is selected again. Pull request:
  https://github.com/Cosmyx/OrcaSlicer/pull/129. Decisions: 0050, 0051, 0052,
  0053, 0054, 0055, 0223.

<!-- cosmyx-slot: T6 -->
- Show the version as `<OrcaSlicer version>-<Cosmyx patch>` (for example
  `2.6.0-8`, or `2.6.0-dev-8` on a development base; the patch starts at 8)
  in the About dialog, the splash screen, the network test and the
  troubleshoot dialogs, and name CI builds and artifacts
  `<that version>_<short commit hash>`. Pull request: pending.
  Decisions: 0060, 0061, 0062, 0063, 0064.

<!-- cosmyx-slot: T7 -->
- Stealth mode is always on: no cloud login, profile sync or online vendor
  update, whatever the Preferences or the login dialog say, and the setup
  guide finishes without the stealth mode and network plugin pages. Pull
  request: pending. Decisions: 0070, 0071, 0072, 0073.

<!-- cosmyx-slot: T11b -->
- Ship the CosmoSlice application icon, About dialog logos and splash
  screen in Cosmyx builds: 11 files vendored from CosmoSlice (window,
  taskbar and Linux desktop icons, About banner, splash) and 6 rasters
  derived from the CosmoSlice SVG master by `just brand-derive` in a pinned
  resvg image (multi-size Windows icon, macOS app icon, MSIX tiles). The
  other logos (file-type icons, bed texture, web and dialog logos) keep the
  Orca files for now. Pull request: #101. Decisions: 0124, 0125, 0126.

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
- Translate the Cosmyx strings: per-feature catalogues under
  `localization/cosmyx/` (cht-nozzle, ironing-temperature, models) for every
  OrcaSlicer language, seeded from the previous Cosmyx branch, grafted into
  the OrcaSlicer catalogues by every desktop build, Flatpak included (its
  job hooked in whichever workflow file the upstream base keeps it, its
  container workspace trusted for git), without marking the build "-dirty"
  (the edited files are hidden from git diff).
  Recipes `just i18n-extract`, `i18n-seed`, `i18n-graft`, `i18n-ungraft`,
  `worktree-hidden`. The graft accepts UTF-8 catalogues only, reads strings
  holding Unicode line separators, and never glues an entry to a catalogue
  without a final newline. A script test fails when the catalogues are out of
  date with the sources, and `just i18n-coverage` lists the missing
  translations (a gate with `COSMYX_I18N_STRICT=1`). Pull request: pending. Decisions: 0080, 0081, 0082
  (superseded), 0083, 0084, 0085, 0086, 0087, 0088.

### CI-release

<!-- cosmyx-slot: T9 -->
- Sign Windows builds of DEV and `release/*` with Azure Artifact Signing:
  the app, the installer's payload, the uninstaller and the installer are
  signed and timestamped, then checked; a signed build that wrote no
  installer (`OrcaSlicer_` or `CosmoSlice_` prefix) fails. Uses the repository's existing
  `AZURE_*` signing secrets and is off without them. Action needed: add an
  Entra federated credential per signed branch (subject
  `repo:Cosmyx/OrcaSlicer:ref:refs/heads/DEV`, and each `release/*`), see
  `wiki/cosmyx/windows-signing.md`. Pull request: pending. Decisions: 0090,
  0092, 0094, 0095, 0097, 0098, 0099.

<!-- cosmyx-slot: T10 -->
- Add the scheduled upstream sync: every two hours `Orca-Upstream` mirrors
  upstream `main`, `MIXED` is rebuilt as `DEV` merged with it (a conflict fails
  the run and lists the files), `build_all` runs on `MIXED` when it moved, and
  the upstream bots are kept disabled by a scheduled workflow policy. Needs the
  `UPSTREAM_SYNC_TOKEN` secret. Pull request: https://github.com/Cosmyx/OrcaSlicer/pull/87. Cosmyx-owned
  `cosmyx-*.yml` workflows may be scheduled without a policy entry. Decisions:
  0100, 0101, 0102, 0103, 0104, 0105.

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
  release builds stay strict (`just brand-mode`, `brand-apply tolerant`); a
  local `integration/<tag>` checkout and its real-tree tests are tolerant too. Recipes `just brand-check`, `brand-apply`, `brand-revert`,
  `brand-sync`, `brand-refresh`, `brand-validate` (user only), `brand-table`;
  workflow in `wiki/cosmyx/branding.md`. Pull request: pending. Decisions:
  0120, 0121, 0122, 0123.

<!-- cosmyx-slot: T13 -->
