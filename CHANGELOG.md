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

<!-- cosmyx-slot: T17 -->
- **Breaking:** user data now lives under a `Cosmyx` folder on every OS
  (`%APPDATA%\Cosmyx\OrcaSlicer`, `~/Library/Application Support/Cosmyx/OrcaSlicer`,
  `~/.config/Cosmyx/OrcaSlicer`), apart from upstream OrcaSlicer. Nothing is
  migrated, not even upstream's legacy Flatpak data: presets, login and plugins
  from the old folder must be set up again (Cosmyx builds that already used `Cosmyx\OrcaSlicer` on Windows and macOS keep
  theirs). The Windows installer installs to `Program Files\Cosmyx\CosmoSlice`
  under the uninstall key `Cosmyx CosmoSlice`, side by side with upstream
  OrcaSlicer, and removes an earlier Cosmyx install only when its key and
  publisher identify it as Cosmyx. Pull request: pending. Decisions: 0180,
  0181, 0182, 0183, 0184.

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

<!-- cosmyx-slot: T12 -->
- Cosmyx code logs to its own file, `cosmyx_<session>.log` next to Orca's
  debug log, through `COSMYX_LOG(level)`; upstream log records and files are
  unchanged. Pull request: pending. Decisions: 0110, 0111.

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
- Ship the remaining CosmoSlice logos in Cosmyx builds: 11 files vendored
  from CosmoSlice (bed texture, gradient and gray logos, configuration
  wizard and unreferenced logos) and 6 rasters derived from the SVG master
  (macOS document, G-code and STL file-type icons, grayscale message logo,
  title logo, web header logo). The horizontal Troubleshoot logos and
  `web/image/logo2.png` are still missing. Pull request: #130.
  Decisions: 0124, 0125.

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
- Propose violet versions of the teal SVG icons for review: `just
  brand-candidates` recolours them with the validated colour mappings into
  `build/cosmyx/`, `just brand-review` shows them before and after on the
  light and dark backgrounds, and `just brand-accept` moves the approved ones
  into the overlay as rows to validate. All 524 teal SVG icons are now
  violet in the overlay, validated. On an older upstream base (tolerant
  mode, decision 0122) the icons that tree lacks are left out. Pull request:
  pending. Decision: 0131.

<!-- cosmyx-slot: T11e -->
- Name the application CosmoSlice in every build: window titles, About,
  installers, Start menu and desktop shortcuts, menus, the Flatpak software
  centre name and description, hints, the setup guide, and 144 interface
  texts with their translations in every language (never marked fuzzy).
  The cloud service reads Cosmyx Cloud wherever the interface names it
  (menus, dialogs, tooltips, notifications, the homepage, the setup guide
  and the plugin and preset-export pages), translations included.
  Every package is named CosmoSlice too: the Windows executable
  (CosmoSlice.exe, command alias cosmoslice.exe in the MSIX), the installer,
  portable, MSIX, DMG (volume CosmoSlice), CosmoSlice.app, AppImage and
  Flatpak files, the AppImage launcher, and every CI artifact
  (`CosmoSlice_...`); the profile validator is no longer exported. The app
  key and data folder, OrcaSlicer.conf, the bundle id, the Linux binary
  orca-slicer and the Flatpak id stay OrcaSlicer, and G-code still says
  "generated by OrcaSlicer" so every tool keeps reading it.
  Names written with a grammatical suffix in inflected languages (Czech,
  Hungarian, Basque, Swedish) are renamed from a per-language table written
  by speakers (including the words next to the name that change with it,
  such as the Hungarian article), and reported until their row exists;
  "ORCA SLICER" is renamed
  whole; texts naming the config file or the Windows data folder keep
  pointing at their real OrcaSlicer names, and texts naming the .app or the
  AppImage follow their CosmoSlice names. A guard fails the build if the
  AppImage launcher name and the file made from it disagree, or if the
  rename changes a packaging name the build scripts rely on.
  The renamed CosmoSlice.app is sealed (ad hoc when the build is unsigned)
  and verified before it goes into the DMG, so macOS no longer reports it
  as damaged; a bundle that does not verify fails the build.
  Exception texts that upstream tests assert (the plugin host's "OrcaSlicer
  application is not initialized") are kept, and a test fails if the rename
  ever rewrites a text an upstream test asserts.
  On an older upstream base (tolerant mode), rename rows whose text that
  tree does not have are skipped with a warning instead of failing the build.
  The same holds for a local integration checkout, and the package-name
  wiring tests skip hook anchors that base lacks and find the Flatpak hook
  in build_all.yml where there is no build_flatpak.yml.
  A guard reports any new upstream text naming OrcaSlicer; recipe
  `just brand-name-candidates` proposes the rows. The cloud web pane and
  the plugin hub fall back to CosmoCloud (orca-cloud.cosmyx3d.fr) instead of
  cloud.orcaslicer.com. Pull request: pending.
  Decisions: 0132, 0133, 0134, 0135, 0201, 0210, 0211, 0212.

<!-- cosmyx-slot: T11f -->
- Always run in dark mode, on Windows, macOS and Linux, for new and existing
  configs alike, whatever the system appearance; macOS and Linux native
  widgets are asked for the dark appearance too. **Removed:** the way back to
  light: the Windows Preferences "Enable dark Mode" toggle no longer has any
  effect. Pull request: pending. Decisions: 0136, 0137, 0138, 0139.

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

<!-- cosmyx-slot: T16 -->
- Pin every screen to GUI goldens on Linux, macOS and Windows: an in-app
  driver, started only when `COSMYX_GUI_DRIVER_DIR` is set, walks the built
  application through every main tab, menu, Preferences tab, settings page,
  catalog command and calibration dialog, then slices the cube from the
  interface; the harness captures each screen and compares it with
  `tests/cosmyx/gui/goldens/<os>/` (Linux byte-exact in a pinned Docker image,
  Windows and macOS within a recorded tolerance). Every Build all run gets
  the `cosmyx/gui-goldens` status; the first golden set is generated by CI.
  The harness runs both the CosmoSlice-named builds (`CosmoSlice.exe`,
  `CosmoSlice.app`, `CosmoSlice_` artifacts) and the older OrcaSlicer-named ones.
  Pull request: pending. Decisions: 0162 to 0179.

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
  plugin signing settings and messages are translated into French, and
  machine-translated for review into the 20 other offered UI languages.
  Pull request: https://github.com/Cosmyx/OrcaSlicer/pull/112. Decision: 0204.

### i18n

<!-- cosmyx-slot: T8 -->
- Fill the Cosmyx catalogues in all 22 OrcaSlicer languages (CHT nozzle,
  ironing temperature, Cosmyx models), using each language's OrcaSlicer terms
  for shared words. Pull request: pending.
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
- Check every "Build all" run's artifacts on their own OS: Windows signatures
  and installer payload, macOS architectures and arm64 signatures, Linux ELF
  files with a smoke run and a slice, plus the build tag in the names and the
  shipped translations and models. Posts the commit status
  `cosmyx/artifact-checks`; signatures are enforced only on signed builds (see
  `wiki/cosmyx/artifact-checks.md`). File names and tool output from a build
  cannot forge the summary or break junit.xml, and a damaged package or
  undecodable output is a failed check, not a crashed job. Artifacts named
  `OrcaSlicer_*` or `CosmoSlice_*` (with `orca-slicer.exe` or `CosmoSlice.exe`)
  are both accepted, and a build without the profile validator passes. Pull
  request: pending. Decisions: 0140, 0141, 0142, 0143, 0144, 0145, 0146, 0147, 0148,
  0149.

<!-- cosmyx-slot: T15 -->
- Sign DEV and `release/*` macOS builds with the Cosmyx Developer ID
  certificate, notarise and staple the apps and the DMGs, and verify them
  before upload; each DMG keeps the name of the app it holds
  (`CosmoSlice_Mac_universal_<ver>.dmg` for `CosmoSlice.app`). The artifact checks then
  enforce Developer ID, team, notarisation and stapling on those DMGs. Uses
  the repository's existing Apple signing secrets and is off without them;
  the app-specific password never appears on a command line. Pull request:
  pending. Decisions: 0150, 0151, 0152, 0153, 0154, 0155, 0156, 0157, 0158,
  0159.

<!-- cosmyx-slot: T16a -->
- Run the Windows x64 and macOS apps after every "Build all" run, as on Linux:
  `--help` and a slice of the shipped cube, judged on the G-code it writes. On
  Windows the app runs from a temporary copy with a pinned, hash-checked Mesa
  software OpenGL (mesa-dist-win 26.2.5, MIT, test-only, never shipped). The
  macOS run never executes a file outside the app bundle. The Windows run
  starts `CosmoSlice.exe`, or `orca-slicer.exe` for an unrenamed build, and
  fails naming both when neither is there. See
  `wiki/cosmyx/artifact-checks.md`. Pull request: pending. Decisions: 0160,
  0161.
