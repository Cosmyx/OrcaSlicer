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

## Expected on v2.5.2 (not yet confirmed by a run)

Upstream `v2.5.2` (`f92a7c065c`) is `v2.5.1` plus 44 commits of the 2.5 release branch (backports, a translation
refresh, deps fixes). It is not an ancestor of `DEV` (229 commits only in the tag, 310 only in DEV; merge-base
`65aab6bcf7`). The dry run of 2026-11-23 met only the v2.5.1 conflicts again (see the log); the combined tree equals
`integration/v2.5.1` plus the tag diff plus `04f9955f54`. What is left needs the build of `integration/v2.5.2` (run
45136685686) or the artifact checks.

Already confirmed by the v2.5.1 build (run 44716244843), and expected to hold: Linux x86_64 and aarch64, macOS arm64
and x86_64 and Windows x64 compile and link (so `ColorMode.cpp`, `GoldenDriver.cpp` and `CloudServerPrefs.cpp` build
on the release base, and the wxWidgets fork has `SetAppearance`); Linux unit tests green; Windows artifacts are named
`OrcaSlicer_Windows_2.5.1-8_<8-char hash>_x64` (so `2.5.2-8_<hash>` now); the PDB artifact is named `PDB`.

- **Windows arm64 deps.** Expected green: v2.5.2 carries the OCCT workaround `3cd5a7d19a` (#17601). See the log.
- **Flatpak.** Expected past the runtime update: v2.5.2 carries `2e2becc3f2` (#17207). It also carries `9a4391396c`
  (Boost.Locale configure with CMake 4.5, #17725), which may be the known Boost configure failure; check.
- **macOS unit tests and the Universal job.** Cancelled in the v2.5.1 run (no macOS runner): still unverified.
- **`ci/cosmyx-artifact-checks`: artifact names.** No per-arch `OrcaSlicer_Mac_<arch>_<ver>` DMG on the tag (only
  `OrcaSlicer_Mac_bundle_<arch>_<full sha>`); the `mac-arm64`/`mac-x86_64` regexes match nothing (harmless); check
  `data/expectations.json` against this run's artifact list and `content.py`'s version parsing of `version.inc`.
- **`test/cosmyx-gui-goldens`:** goldens are base-specific (none committed yet); `pick_artifacts` must still find the
  tag's Linux AppImage, macOS DMG and Windows x64 portable artifacts.
- **`ci/cosmyx-exec-smoke`:** re-check `--help` and the slice command line of `slice.py` against the tag's CLI
  (`src/OrcaSlicer.cpp`, which v2.5.2 edits).
- **`feat/cosmyx-windows-signing`:** on the tag the installer payload is signed twice (no `ORCA_SIGN_REUSE` in the
  foreground cpack); valid but slower. Only visible on a signed ref.

## Log

### 2026-11 ci/cosmyx-integration - DEV rebuild with the package names and three new branches
- Symptom: rebuilding `ci/cosmyx-integration` from `origin/DEV` (`3838002bc8`) with every open PR tip (rows 1-28, then
  #111) conflicted in: `build_orca.yml` (macos-signing against product-name's `mac-app` step, same gap after "Create DMG
  without notary"); `test_foundation.py` `SLOTS_BY_AREA` and decision 0003 (install-paths, gui-goldens, cloud-server,
  flatpak-off, raster-images); `CHANGELOG.md` (gui-goldens T16, flatpak-off T19 after T16a); `GUI_App.cpp` (goldens
  include); `wiki/cosmyx/branding-assets/icons-n-z.md` and `web.md` (raster-images against svg-candidates). The manifests
  `icons-n-z.json` and `web.json` merged without a text conflict. plugin-signing merged clean.
- Cause: sibling branches adding slots or steps at the same place; generated tables rewritten by two branches.
- Resolution: `rerere` (cache of the previous integration) replayed `build_orca.yml` (`mac-app` step first, then "Cosmyx
  sign and notarize macOS", identical to the old integration's file) and the install-paths, goldens and cloud-server
  unions. By hand: flatpak-off and raster-images unions (`CI-release` ... T15, T16a, T19; `GUI` ... T11f, T16, T18,
  T11g, the order of the markers in `CHANGELOG.md`), T19 line after T16a's. Tables: `git checkout --ours`, then
  `just brand-sync` (0 added, 0 updated, 0 dropped) and `just brand-table`, in the merge commit; 571 rows `validated`
  before and after (34 logos, 524 svg, 13 rasters), 3 logos `missing`. Checks: `run_script_tests.py` 961 OK (6
  skipped, no pwsh), `just decisions` OK, `brand-check` 0 errors, `brand-apply` (571 overlays) then `brand-revert`,
  tree clean. Lesson: in the integration, regenerate tables in the merge commit, and count `validated` rows.
- Commit: integration tip `36b5a412b5`, build run 45374695673.

### 2026-11 several branches - v2.5.2 pass replays the v2.5.1 resolutions
- Symptom: on v2.5.2 the same conflicts and breaks as on v2.5.1: modify/delete of `build_flatpak.yml` (foundation
  `be423c6998`, translations `abcf9e2295`), the two `build_orca.yml` conflicts of windows-signing, the `Preferences.cpp`
  include of cloud-server, the stale painted-modifier rows (engine, colours), the 13 G8 errors (product-name), the
  four-tab Preferences enum (goldens), and the integration unions (slot lists, decision 0003, CHANGELOG, `GUI_App.cpp`).
- Cause: v2.5.2 is a patch release of the same release branch; none of its 44 commits touch a hook anchor.
- Resolution: `rerere` (cache of the v2.5.1 pass) replayed every textual resolution; the two `build_flatpak.yml` hooks
  were re-applied from the v2.5.1 copies' commits; each adaptation was re-run with its generator (`brand-sync`,
  `brand-colour-literals`) or re-checked (`brand-check`, script test) and gave the same diff as on v2.5.1.
- Commit: `718f663275` (engine), `33fbc1c012` (colours), `e1e7a173f0` (product-name), `da81bbfea6` (goldens), dry-run
  copies.

### 2026-11 feat/cosmyx-svg-candidates - rerere does not replay a file deletion
- Symptom: after the v2.5.2 rebase, `brand-check` failed with G2 "overlay file has no manifest row" for
  `menu_add_painted_modifier.svg`, `toolbar_painted_modifier.svg`, `toolbar_painted_modifier_dark.svg`.
- Cause: rerere replayed the manifest and table text conflicts of the accept commits, but the `git rm` of the three
  overlays was not a text resolution, so the accept commits added them back.
- Resolution: one `git commit --fixup=<accept commit>` per accept commit with the `git rm`, then
  `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <colours tip>`. Lesson: after a rerere-driven rebase, compare
  the Cosmyx-owned tree with the previous copy (`git diff <old copy> HEAD -- cosmyx-src wiki scripts`).
- Commit: none added (folded into the accept commits; copy tip `715c60a6f7`).

### 2026-11 integration/v2.5.1 - Windows arm64 deps: MSVC 14.52 internal compiler error in OCCT
- Symptom: run 44716244843 failed on "Build Windows arm64 / Build Deps" with MSVC 14.52 C1001 (internal compiler error)
  in OCCT `BRepGraph_LayerTopoSupplement.cxx`.
- Cause: a runner image update from MSVC 14.51 to 14.52. Upstream never compiled it for v2.5.1, because its deps came
  from cache; our fork has no deps cache, so it does a full deps build.
- Resolution: upstream fixed it in `e0f7f0b7ee` (#17601), which is in v2.5.2+ (as `3cd5a7d19a`) and in DEV. Lesson: a
  fork builds every dependency from scratch, so a release tag can fail on a newer runner image even though upstream
  shipped it. Check upstream's later release branches (and `main`) for workarounds before dispatching, for example
  `git log --oneline $BASE..upstream/main -- deps .github`.
- Commit: none (upstream fix).

### 2026-11 integration/v2.5.1 - Flatpak runtime update fails with "Invalid cross-device link"
- Symptom: both Flatpak legs of run 44716244843 failed: "Error: Failed to update org.gnome.Sdk: Invalid cross-device
  link", then `xvfb-run` exit code 139.
- Cause: updating a Flatpak runtime renames its old deployment, which fails on a Docker overlay filesystem; like the
  MSVC case, upstream's cache hid it.
- Resolution: upstream mounts `/var/lib/flatpak` as a volume in the `flatpak:` job (`2e2becc3f2`, #17207, in v2.5.2;
  `aee4dfc705` in DEV). Nothing to do on our side.
- Commit: none (upstream fix).

### 2026-11 integration/v2.5.1 - slot lists and shared lines collide between siblings
- Symptom: merging install-paths, gui-goldens and cloud-server into `integration/v2.5.1` conflicted in
  `scripts/cosmyx/tests/test_foundation.py` (`SLOTS_BY_AREA`), `wiki/decisions/0003-changelog-slots.md`, and for
  goldens also `CHANGELOG.md` (T16 next to T11f) and `GUI_App.cpp` (GoldenDriver include on line 4).
- Cause: sibling branches each add their own slot or line at the same place; no feature branch can carry the other's.
- Resolution: union in the merge commit (repo T0, T17; libslic3r adds T12; GUI adds T16, T18; includes version,
  ColorMode, GoldenDriver). `rerere` records it. Integration script tests green afterwards.
- Commit: merge commits of `integration/v2.5.1` (`f9025dc30d`).

### 2026-11 test/cosmyx-gui-goldens - four Preferences tabs on v2.5.1
- Symptom: `test_gui_goldens_script.ScriptTests.test_preferences_tabs_follow_the_upstream_enum` failed on the tag.
- Cause: v2.5.1 `PreferencesTab` is `General, Control, Graphics, Online`; the driver's six names (DEV layout) map by
  index, so wrong tabs and out-of-range values were opened.
- Resolution: `preferences_tabs()` follows the tag's enum, expansion test expects four surfaces, the script test
  compares the enum with the driver list.
- Commit: `124e62829c` (dry-run copy).

### 2026-11 feat/cosmyx-svg-candidates - sync keeps rows that still have an override
- Symptom: after `git rm` of the 3 painted-modifier overlays and `just brand-sync`, the rows stayed (0 dropped),
  and the accept commits conflicted on `icons-*.json` / `icons-*.md` when restacked on the adapted colours.
- Cause: `manifest.sync` never touches a row whose `override_sha256` is set.
- Resolution: per conflicting accept commit, take the replayed side, `git rm` the overlay, `just brand-refresh
  <path>` (override becomes null), then `just brand-sync` and `just brand-table`. 521 overlays remain.
- Commit: none added (resolved inside the accept commits; copy tip `e3f21df2ea`).

### 2026-11 feat/cosmyx-product-name - stale rows on v2.5.1
- Symptom: `brand-check` 13 G8 errors on the tag.
- Cause: 6 msgid rows name DEV-only texts; the plugin permission docstring literal row carries DEV's longer text.
  "Objects (%1%) have duplicated connectors" was wrongly expected stale.
- Resolution: 6 rows dropped, literal row rewritten to the tag's text; `brand-name-candidates` empty.
- Commit: `bbded5e02d` (dry-run copy).

### 2026-11 feat/cosmyx-colours - literal row on a missing file
- Symptom: G5 "cannot read" on `GLGizmoPaintedModifier.cpp` (absent from v2.5.1).
- Cause: DEV-only file.
- Resolution: `just brand-colour-literals` dropped only that row (114 rows); statuses unchanged.
- Commit: `2b46a70b77` (dry-run copy).

### 2026-11 ci/cosmyx-branding-engine - painted-modifier rows on v2.5.1
- Symptom: `CommittedTablesTest.test_every_row_points_at_a_real_file` failed (3 paths); G3 warnings; the same
  failure in every branding child until restacked.
- Cause: three DEV-only icons.
- Resolution: `just brand-sync` (3 dropped), `just brand-table`; logos, colours, product-name restacked on the new
  engine tip, svg-candidates on the new colours tip.
- Commit: `f94c18ee95` (dry-run copy).

### 2026-11 feat/cosmyx-cloud-server - Preferences include block
- Symptom: `88d9f1d0b5` conflicted at the top of `Preferences.cpp`.
- Cause: DEV's line 2 `#include "slic3r/plugin/host/PluginPages.hpp"` is absent from the tag.
- Resolution: keep only the Cosmyx include on line 2; the panel anchor still adjoins the Cloud Providers title.
- Commit: none added.

### 2026-11 feat/cosmyx-windows-signing - DEV-only step context in build_orca.yml
- Symptom: `137f9674b6` conflicted twice in `build_orca.yml`.
- Cause: DEV's "Save signed NSIS plugins" step (above our sign step) and DEV's step order after "Verify Windows
  signatures" do not exist on the tag ("Pack app" and "Pack PDB" sit before "Upload artifacts Win zip").
- Resolution: sign step before "Pack unit tests Win"; verify step directly after upstream's verify. Later commits
  replayed clean; wiring test green.
- Commit: none added.

### 2026-11 chore/cosmyx-foundation, feat/cosmyx-translations - build_flatpak.yml absent from v2.5.1
- Symptom: modify/delete conflicts on `.github/workflows/build_flatpak.yml` (`be423c6998`, `abcf9e2295`).
- Cause: DEV split the Flatpak job out of `build_all.yml` after the release (`a4de8cb891`).
- Resolution: `git rm`; asset hook on the `find "$d/resources"` line of `build_all.yml`, prepare hook after the
  `flatpak:` job's checkout; foundation test reads `build_all.yml`; decision 0005 names both files.
  `build_all.yml` is CRLF upstream: edit as bytes, keep CRLF.
- Commit: none added.

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

## Skill gaps found

Found on the v2.5.2 dry run (2026-11-23):

- No path for a target that follows a previous pass (a patch release such as v2.5.1 to v2.5.2). What worked: compare
  each `origin/<branch>` with the previous copy's source (`git reflog rebase/<old tag>/<branch>`, then
  `git range-diff <old NP>..rebase/<old tag>/<b> <OLD>..origin/<b>`) to see which branches really changed; let `rerere`
  replay the old resolutions; re-run each adaptation's generator and check its diff equals the old adaptation commit.
  The whole pass then takes minutes. Old copies and the `rerere` cache are worth keeping until the next pass.
- The skill's commands use `rerere.enabled` only: a rebase still stops at every conflict rerere has already resolved.
  `-c rerere.autoupdate=true` plus a loop that continues while no file is unmerged lets one script replay a branch.
- `rerere` replays text resolutions, not file deletions (`git rm` of an overlay, of `build_flatpak.yml`); a deletion is
  re-done by hand, inside the commit it belongs to (`--fixup` + `rebase -i --autosquash` with
  `GIT_SEQUENCE_EDITOR=true`). The skill does not mention it.
- Step 8 dispatches the build without checking that the target builds from scratch on today's runner images. A fork has
  no deps cache, so it meets compiler and runner breakages upstream's cache hid (MSVC 14.52 ICE, Flatpak runtime
  update). Before dispatching, look for upstream build workarounds after the tag:
  `git log --oneline $BASE..upstream/main -- deps .github` and the later release branch.
- Step 4's `git range-diff` proof marks context-only changes as `!` (a CHANGELOG neighbour line); the skill should say
  to read each `!` pair rather than treat it as a changed patch.
- The scratchpad may hold files from other sessions; keep a per-pass subfolder for scripts and logs.

Found on the v2.5.1 dry run (2026-11-20); what `SKILL.md` and the sheets did not say (still open unless noted):

- Step 1's `git fetch ... "refs/tags/$TAG:refs/tags/upstream/$TAG"` breaks under zsh: `$TAG:r` is a modifier and
  the refspec becomes `refs/tags/v2.5efs/...`. Write `${TAG}:refs/...` (the zsh note only mentions `$b:path`).
- Upstream `build_all.yml` (and other workflows) are committed with CRLF; a text-mode edit rewrites every line.
  Hooks in CRLF files must be edited as bytes.
- Branding children are stacked: after an adaptation commit on the engine (or colours), every child must be rebased
  again onto the new parent tip, and the step order (rebase all, then adapt) should be "rebase and adapt each parent,
  then its children".
- `brand-sync` does not drop a row that has an override; dropping an overlay row needs `git rm`, `brand-refresh
  <path>`, then `brand-sync` (the previous expectation said `brand-sync` alone).
- Step 7 says every integration conflict is fixed in a feature branch, but union conflicts between siblings
  (slot lists, decision 0003, CHANGELOG neighbours, `GUI_App.cpp` include block) can only be resolved in the merge
  commit; `branches.md` now says so for the slot lists.
- The product-name stale rows were not the expected list (6 msgid + 1 literal, not 7 msgid); expectations derived
  from a DEV snapshot drift as DEV moves: recheck with `cli.py check` instead of trusting the list.
- Step 5 runs the full script suite per branch: about 3 minutes each on the share; `timeout(1)` does not exist on
  macOS. Running the 25 suites in one background loop works.
- The worktree per branch costs about 3 s here (no need to reuse one worktree).
- The skill gives no way to check Flatpak hooks: no test pins the translations prepare hook in `build_all.yml`.
- Artifact checks and goldens need a finished build; the dry-run brief stops at dispatch, so these stay open.
- The report template says "save REPORT.md"; a subagent cannot write report files, the report goes in the final
  message only.
