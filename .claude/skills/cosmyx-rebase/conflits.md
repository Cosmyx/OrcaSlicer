# Conflicts and breaks

Everything a rebase, a merge or a CI run of the Cosmyx branches has broken, and how it was fixed. Read it
before a pass; prepend to the log after one (newest first).

Entry format:

```markdown
### <YYYY-MM> <branch> - <short title>
- Symptom: what failed, where (job, OS, test name).
- Cause: why.
- Resolution: what was changed, in which branch; the lesson if any.
- Commit: <sha> (or "unknown").
```

## Expected on v2.5.1 (not yet confirmed by a run)

Upstream `v2.5.1` (`eef7710cb1`) is not an ancestor of `DEV` (185 commits only in the tag, 310 only in DEV;
merge-base `65aab6bcf7`). The sheets checked every anchor against the tag; these are the places expected to
need work. Move each item to the log once a run confirms it.

- **`chore/cosmyx-foundation`, `be423c6998`: modify/delete on `.github/workflows/build_flatpak.yml`.** The file
  does not exist in v2.5.1 (DEV split it out of `build_all.yml` later, `a4de8cb891`). Do not recreate it:
  `git rm` it and add `! -name cosmyx ! -name info` plus the comment
  `# Cosmyx: cosmyx_tests also reads resources/cosmyx and resources/info.` to the
  `find "$d/resources" -mindepth 1 -maxdepth 1 ! -name profiles ! -name printers ! -name images -exec rm -rf {} +`
  line of `.github/workflows/build_all.yml` (line ~489 on the tag). Point `FlatpakTestAssetTests` and
  `FlatpakTestTargetTests` in `scripts/cosmyx/tests/test_foundation.py` at `build_all.yml`. Check that
  `libslic3r_tests` is still in the target list of `scripts/flatpak/com.orcaslicer.OrcaSlicer.yml`.
  `cosmyx-checks.yml` lists `build_flatpak.yml` in `paths:`: harmless; change it only if `ChecksWorkflowTests`
  fails.
- **`feat/cosmyx-translations`: Flatpak prepare hook anchor gone.** Same cause. Move the two lines
  `- name: Prepare Cosmyx sources # Cosmyx` / `uses: ./.github/actions/cosmyx-prepare # Cosmyx` into the inline
  `flatpak:` job of `build_all.yml`, directly after its `    - uses: actions/checkout@v7` (line ~299 on the tag,
  before "Get the version and date"), with the job's indentation. The `build_orca.yml` hook (after `Checkout`,
  before `load cached deps`) applies as is.
- **`ci/cosmyx-branding-engine` and `feat/cosmyx-svg-candidates`: three icons absent from v2.5.1**
  (`resources/images/menu_add_painted_modifier.svg`, `toolbar_painted_modifier.svg`,
  `toolbar_painted_modifier_dark.svg`, DEV-only). On the engine branch the rows are `missing`: run
  `just brand-sync` (drops them) and `just brand-table`, commit. On svg-candidates the rows carry overlays:
  `git rm` the three files under `cosmyx-src/branding/overlay/resources/images/`, then `just brand-sync` and
  `just brand-table`, commit. Until then
  `test_branding_manifest.CommittedTablesTest.test_every_row_points_at_a_real_file` fails and G3 warns (dev) or
  fails (release).
- **`feat/cosmyx-colours`: literal row on a missing file.** `src/slic3r/GUI/Gizmos/GLGizmoPaintedModifier.cpp`
  (`ImVec4(0.f, .59f, .53f` x3) does not exist in v2.5.1, so G5 errors ("cannot read") and the build is refused
  on every build kind. Run `just brand-colour-literals`; the diff of `colours.json` must only drop that row
  (114 rows remain). Statuses untouched.
- **`feat/cosmyx-product-name`: stale msgid rows.** 7 `rename.json` msgid rows and 1 `allowlist.json` msgid row
  are not in the v2.5.1 `OrcaSlicer.pot` (stale row = G8 error on every build). Known ones: "Each object in the
  file is loaded on its own, as OrcaSlicer always loaded AMF files.", "Objects (%1%) have duplicated
  connectors. ...", "Some original names contain characters that OrcaSlicer cannot use...", "The following
  settings refer to plugins Orca Slicer can't identify on this computer...", "The presets being saved refer to
  plugins Orca Slicer can't identify...", "Use the body names stored in the file, when there are any...".
  Remove them (or rewrite to the tag's wording) and run `just brand-name-candidates` for new texts. The 34 patch
  rows match v2.5.1 exactly.
- **`feat/cosmyx-windows-signing`: older signing flow in v2.5.1.** No `ORCA_SIGN_REUSE`, no "Restore/Save signed
  NSIS plugins", no "Start installer Win" (the installer is built by a foreground "Create installer Win" with
  `cpack -G NSIS`). Place "Cosmyx sign Windows binaries" right before "Pack unit tests Win" (there is a "Build
  system preset cache (Windows)" step between "Build slicer Win" and the Google auth on the tag); setup before
  "Build slicer Win"; verify after "Verify Windows signatures". The installer payload is signed twice (valid,
  slower). The `sign_windows.ps1` dispatch line after `$ErrorActionPreference = 'Stop'` applies.
- **`ci/cosmyx-upstream-sync`: workflow set.** v2.5.1 lacks `stale.yml` and `wait-for-response-label.yml`;
  `workflow-policy.json` lists a superset (tolerated). Run
  `test_repository_policy_covers_every_scheduled_workflow`; add any new scheduled workflow of the tag to the
  JSON. The sync keeps tracking `main`, never the tag.
- **`ci/cosmyx-artifact-checks`: artifact names.** Tag names the PDB artifact `PDB` (DEV `PDB_msvc` for MSVC)
  and has no per-arch `OrcaSlicer_Mac_<arch>_<ver>` DMG. The `mac-arm64`/`mac-x86_64` regexes match nothing
  (harmless); check `data/expectations.json` against a real run's artifact list and `content.py`'s version
  parsing of `version.inc`.
- **`feat/cosmyx-version`: display version.** `version.inc` says `2.5.1`, so the display version is `2.5.1-8`
  (patch 8) and the build tag `2.5.1-8_<hash>`; `python3 scripts/cosmyx/cosmyx_version.py version` must print
  it. The step goes after "Get the version and date on Windows" (ends `shell: pwsh`, then `#   Mac`).
- **`feat/cosmyx-install-paths`: context of the Flatpak migration hook.** On the tag the guard is
  `if(!boost::filesystem::exists("/.flatpak-info")) return;` (DEV: `if (!is_running_in_flatpak()) return;`). The
  hook is a pure insertion after that `return;` line; resolve by keeping the tag's line and adding the hook below.
- **`feat/cosmyx-dark-default`: wxWidgets API.** `wxApp::SetAppearance` needs the wxWidgets 3.3 fork; check the
  tag's `deps` wx pin if macOS or Linux fails to compile `ColorMode.cpp`.
- **`test/cosmyx-gui-goldens`:** goldens are base-specific (none committed yet); `pick_artifacts` must still find
  the tag's Linux AppImage, macOS DMG and Windows x64 portable artifacts.
- **`ci/cosmyx-exec-smoke`:** re-check `--help` and the slice command line of `slice.py` against the tag's CLI
  (`src/OrcaSlicer.cpp`).
- **`feat/cosmyx-cloud-server`:** `Preferences.cpp` differs 241/415 lines from DEV: check that
  `g_sizer->Add(item_network_test);` and the "Cloud Providers" title still adjoin.
- Low risk, hooks apply with line offsets only: bed-temp-off, cht-nozzle, ironing-temperature (4 `GCode.cpp`
  hooks, statements unchanged), toolchange-fan-order, models, stealth-mode, logs (`g_log_sink` still a global of
  the same type), macos-signing ("Create DMG without notary" then "Delete intermediate per-arch artifacts"
  present), logos (37/37 hashes match), translations-fill.

## Log

### 2026-11 feat/cosmyx-cloud-server - hook-count test broken by another feature
- Symptom: `test_cloud_server.StealthHookTests.test_only_two_hook_lines` failed on the combined tree.
- Cause: it counted every `// Cosmyx` line in `AppConfig.cpp`; with dark-default merged there are 4.
- Resolution: count only the stealth lines (`StealthMode` / `stealth_mode`). Lesson: a hook-count test filters
  by its own feature. Same risk in `Preferences.cpp` (2 lines asserted).
- Commit: `ed15f92456`.

### 2026-11 feat/ironing-temperature - libslic3r link closure
- Symptom: `generate_system_cache` and other small tools failed to link on Linux x86_64 and aarch64 with
  undefined `nsvgParse`, `nsvgParseFromFile`, `nsvgDelete`.
- Cause: `PrintConfig.cpp` calls `extend_print_config_def`, pulling `IroningTemperature.o` into every program;
  that file called GCode code, which dragged `GCode.o` and the 3MF/SVG code in.
- Resolution: G-code helpers moved to `IroningTemperatureGCode.cpp`; a Cosmyx file extending `PrintConfigDef`
  must not include GCode headers, guarded by `scripts/cosmyx/tests/test_libslic3r_link_closure.py`.
- Commit: `685b434cb4`.

### 2026-11 feat/cosmyx-product-name - Linux AppImage not produced
- Symptom: integration build 44545583808 produced no AppImage.
- Cause: renaming the desktop entry `Name=` made appimagetool write `CosmoSlice-<arch>.AppImage`, the script
  moves `OrcaSlicer-<arch>.AppImage`.
- Resolution: patch row removed; `PACKAGING_PINS` added to guard G8 (packaging names must be identical after
  apply).
- Commit: `9af4ed8f4c`.

### 2026-11 feat/cosmyx-product-name - renamed a string upstream tests assert
- Symptom: upstream plugin host tests (`tests/slic3rutils/test_plugin_host_api.cpp`) failed on every branded
  build.
- Cause: the rename row for "OrcaSlicer application is not initialized" rewrote exceptions the tests compare
  verbatim.
- Resolution: row dropped, the six literals allowlisted as `compared`; a script test now fails if a rename
  row's old text appears in a non-Cosmyx test.
- Commit: `4199d85961`.

### 2026-11 several branches - Windows CRLF checkouts
- Symptom: script tests failed only on the Windows runner (LF checks, regexes with `^...$`, rows "stale",
  tables "non-canonical", mixed endings written).
- Cause: `core.autocrlf` checks text out as CRLF.
- Resolution: read text as LF and write back with the file's dominant ending; LF checks read the committed blob
  (`git cat-file`); real-tree tests build explicit LF and CRLF copies (`CrlfRealTreeTest`). Lesson: every
  script test reading a file normalises line endings.
- Commit: `4601573750` (sync), `c34bce56ac` (version), `73321ba242` (translations), `2b0c26555e` and
  `ba5ef945d2` (engine), `c9a1d85718` (colours), `5582952b19` (product-name), `7f51119c40` (install-paths).

### 2026-11 ci/cosmyx-artifact-checks, ci/cosmyx-exec-smoke - signal numbers per OS
- Symptom: import error on the Windows runner; wrong crash names on macOS.
- Cause: the crash table used the host `signal` module; Windows has no `SIGBUS`, Darwin numbers SIGBUS 10.
- Resolution: fixed per-target-OS signal tables.
- Commit: `0f40efe642`, `fcf2a4cc91`.

### 2026-11 several branches - compile errors and incomplete test fixtures
- Symptom: C++ did not compile in CI, or tests passed or failed for the wrong reason.
- Cause and resolution:
  - cht-nozzle: `ConfigDef::get()` returns const; take the mutable definition from
    `def.options.find("nozzle_type")` (`08d8d62f96`).
  - gui-goldens: `MainFrame` has no `menubar()`, use `wxFrame::GetMenuBar`; the 3D canvas needs
    `#include <wx/glcanvas.h>` (`6ee87da92f`).
  - bed-temp-off (T1): fixture needs `layer_change_gcode = G92 E0`, else `Print::validate()` stops at the G92
    check first (`de8058dc33`).
  - toolchange-fan-order (T4): two-filament fixture must set `filament_extruder_variant` and
    `filament_self_index` for both filaments (`e9ab15ae0f`).
  - product-name: G-code header fixture must serialise a full config (>= 80 keys) (`adad18b959`).
- Commit: as listed.

### 2026-11 feat/cosmyx-install-paths - upstream XDG test
- Symptom: upstream `[utils]` test "default_data_dir is the XDG config dir without a portable data_dir folder"
  failed on every Cosmyx Linux build.
- Cause: the data folder moved under `Cosmyx/`.
- Resolution: two-line tagged hook in `tests/libslic3r/test_utils.cpp` expecting
  `vendor_app_subdir(SLIC3R_APP_KEY)` (decision 0185, explicit exception to "no edits to upstream tests").
- Commit: `28aa25e538`.

### 2026-11 chore/cosmyx-foundation - cosmyx_tests in the Flatpak leg
- Symptom: `cosmyx_tests_NOT_BUILT` in the Flatpak test leg; then Cosmyx tests reading models and the nozzle
  table failed there only.
- Cause: the Flatpak leg builds an explicit target list; its test asset deleted `resources/cosmyx` and
  `resources/info`.
- Resolution: `add_dependencies(libslic3r_tests cosmyx_tests)`; keep both folders in the asset (decision 0005).
- Commit: `41b887876e`, `be423c6998`.

### 2026-11 several branches - git "dubious ownership" in job containers
- Symptom: exit 128 in the Flatpak container (graft, branding revert, overlay test).
- Cause: the workspace is owned by another user inside the container.
- Resolution: the prepare action sets `safe.directory` first (pinned by a test); git's own message is reported
  instead of a bare error.
- Commit: `2689120329` (translations), `06adfd16a9` (engine), `c2aff26fbd` (logos).

### 2026-11 ci/cosmyx-branding-engine, feat/cosmyx-logos - arm64 Linux leg
- Symptom: "exec format error" on the arm64 Linux build leg.
- Cause: a branding test built the amd64-pinned resvg image inside the prepare action.
- Resolution: `COSMYX_TEST_PROFILE=prepare` with `skip_in_prepare`; the fresh-render test skips with the
  daemon's reason where amd64 cannot run.
- Commit: `a032fcc90f`, `73d7679e4f`.

### 2026-11 feat/cosmyx-windows-signing - wiring test on a combined tree
- Symptom: the signing wiring test failed once other branches added `# Cosmyx` steps to `build_orca.yml`.
- Cause: it assumed its three steps were the only Cosmyx steps.
- Resolution: steps selected by name, order and uniqueness checked.
- Commit: `a2fbaba0fa`.

### 2026-11 Flatpak - dependency build failure
- Symptom: the Flatpak build fails while configuring Boost in the deps.
- Cause: not investigated.
- Resolution: none yet; Flatpak is excluded from the RDY2MERGE gate and reported separately.
- Commit: unknown.
