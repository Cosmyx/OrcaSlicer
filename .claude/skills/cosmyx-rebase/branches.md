# Cosmyx branches

Every Cosmyx feature branch of `Cosmyx/OrcaSlicer`, how they stack, and how shared files are resolved.
Branch names are on `origin`. All PRs target `DEV`. The "#" column is the rebase order and the integration
merge order (parents always come before children).

## Branches

| # | Branch | PR | What it does | Parent | Other dependencies | Sheet |
|---|--------|----|--------------|--------|--------------------|-------|
| 1 | `chore/cosmyx-foundation` | #86 | Cosmyx module folders and their 5 one-line hooks, `extend_print_config_def` seam, `cosmyx_tests` suite, justfile, script test runner, decision register, changelog slots, `cosmyx-checks` workflow, flatpak test fixes. | `DEV` | none; every other branch depends on it | [sheet](features/chore-cosmyx-foundation.md) |
| 2 | `ci/cosmyx-upstream-sync` | #87 | Scheduled mirror of upstream `main` to `Orca-Upstream`, `MIXED` = DEV + upstream rebuilt and built, scheduled-workflow policy. | `DEV` | foundation | [sheet](features/ci-cosmyx-upstream-sync.md) |
| 3 | `feat/bed-temp-off` | #88 | Bed temperature -1 = heater off (`M140 S0` once, never wait, placeholders clamped). | `DEV` | foundation | [sheet](features/feat-bed-temp-off.md) |
| 4 | `feat/cht-nozzle` | #89 | CHT nozzle type (HRC 65) in `nozzle_type`. | `DEV` | foundation; strings in translations' `cht-nozzle` catalogue | [sheet](features/feat-cht-nozzle.md) |
| 5 | `feat/ironing-temperature` | #90 | Per-filament ironing temperature, range validation of Cosmyx options, libslic3r link-closure test. | `DEV` | foundation; strings in translations' `ironing-temperature` catalogue | [sheet](features/feat-ironing-temperature.md) |
| 6 | `fix/toolchange-fan-order` | #91 | Write `Tn` before the new tool's fan speed; hold a fan resume until after the tool change. | `DEV` | foundation | [sheet](features/fix-toolchange-fan-order.md) |
| 7 | `feat/cosmyx-models` | #92 | "Cosmyx 3D Models" context submenu, calibration models and Calage 3 modifiers. | `DEV` | foundation; strings in translations' `models` catalogue; ships `resources/cosmyx/models/cosmyx_cube.3mf` used by artifact checks | [sheet](features/feat-cosmyx-models.md) |
| 8 | `feat/cosmyx-version` | #93 | Display version `<SoftFever_VERSION>-<patch>`, CI build tag `<version>_<hash>`. | `DEV` | foundation | [sheet](features/feat-cosmyx-version.md) |
| 9 | `feat/cosmyx-stealth-mode` | #94 | Stealth mode forced on, setup guide skips stealth and network-plugin pages. | `DEV` | foundation | [sheet](features/feat-cosmyx-stealth-mode.md) |
| 10 | `feat/cosmyx-translations` | #95 | Cosmyx catalogues grafted into the upstream `.po` files at build time (`cosmyx-prepare` action), skip-worktree helper. | `DEV` | foundation | [sheet](features/feat-cosmyx-translations.md) |
| 11 | `feat/cosmyx-windows-signing` | #96 | Azure Artifact Signing backend behind `scripts/sign_windows.ps1`, three `build_orca.yml` steps. | `DEV` | foundation | [sheet](features/feat-cosmyx-windows-signing.md) |
| 12 | `feat/cosmyx-logs` | #97 | Own Boost.Log channel and `cosmyx_*.log` file, no upstream hook. | `DEV` | foundation | [sheet](features/feat-cosmyx-logs.md) |
| 13 | `feat/cosmyx-dark-default` | #98 | Dark mode forced on every OS, `dark_color_mode` pinned. | `feat/cosmyx-version` | foundation; `GUI_App.cpp` include line 3 after version's line 2 | [sheet](features/feat-cosmyx-dark-default.md) |
| 14 | `ci/cosmyx-branding-engine` | #99 | Build-time branding engine (manifest, overlay, guards G1-G8, apply/revert). | `feat/cosmyx-translations` | foundation; prepare action and `worktree_clean.py` of translations | [sheet](features/ci-cosmyx-branding-engine.md) |
| 15 | `feat/cosmyx-logos` | #101 | CosmoSlice logos vendored and derived into the overlay (34 files, `validated` by the user in `98cebb719f`; 3 rows still `missing`). | `ci/cosmyx-branding-engine` | none beyond the chain | [sheet](features/feat-cosmyx-logos.md) |
| 16 | `feat/cosmyx-colours` | #102 | Teal to violet colour stage (`colours.json`, 24 validated mappings, 115 literal rows). | `ci/cosmyx-branding-engine` | assumes dark mode forced (#98, decision 0139) | [sheet](features/feat-cosmyx-colours.md) |
| 17 | `feat/cosmyx-product-name` | #103 | Product renamed CosmoSlice at build time (patches, msgid renames, inflections), cloud URL fallback rows; CosmoSlice package names (`CosmoSlice.exe`, installer, DMG, AppImage, MSIX, Flatpak, CI artifacts) through `.github/actions/cosmyx-package-names`, `scripts/cosmyx/package_names.py` and `packages.json`, five hook steps `mac-app`, `mac-upload`, `windows`, `linux`, `flatpak`; profile validator no longer exported; MSIX identity by repository variables (decisions 0210-0212). | `ci/cosmyx-branding-engine` | T8 `.po` parser (translations); install-paths' `Packaging.cmake` display-name guard; carries cloud-server's 4 URL rows | [sheet](features/feat-cosmyx-product-name.md) |
| 18 | `feat/cosmyx-svg-candidates` | #110 | 524 recoloured SVG icons accepted into the overlay (`validated` by the user in `9a9034d1a9`), candidate tool. | `feat/cosmyx-colours` | `colours.json` validated mappings (hash in each row) | [sheet](features/feat-cosmyx-svg-candidates.md) |
| 19 | `feat/cosmyx-translations-fill` | #108 | Every Cosmyx catalogue entry translated in 22 languages (data only). | `feat/cosmyx-translations` | none | [sheet](features/feat-cosmyx-translations-fill.md) |
| 20 | `ci/cosmyx-artifact-checks` | #100 | Post-build artifact inspection per OS, commit status `cosmyx/artifact-checks`. | `DEV` | foundation (incl. `92830e0a8b`); reads `CosmyxVersion.hpp` (version), `localization/cosmyx/` (translations), `cosmyx_cube.3mf` (models), signing predicate (windows-signing decision 0098) | [sheet](features/ci-cosmyx-artifact-checks.md) |
| 21 | `ci/cosmyx-macos-signing` | #105 | Developer ID signing, notarisation, stapling of macOS app and DMGs. | `ci/cosmyx-artifact-checks` | none beyond the chain | [sheet](features/ci-cosmyx-macos-signing.md) |
| 22 | `ci/cosmyx-exec-smoke` | #104 | Windows and macOS apps launched and slicing the cube after each build; pinned Mesa for Windows. | `ci/cosmyx-macos-signing` | `cosmyx_cube.3mf` (models) | [sheet](features/ci-cosmyx-exec-smoke.md) |
| 23 | `feat/cosmyx-install-paths` | #106 | Data folder under `Cosmyx/`, Windows installer identity `Cosmyx CosmoSlice`, legacy removal. | `DEV` | foundation; appends after windows-signing's NSIS include; product-name appends `CPACK_NSIS_DISPLAY_NAME` | [sheet](features/feat-cosmyx-install-paths.md) |
| 24 | `test/cosmyx-gui-goldens` | #107 | In-app GUI driver and per-OS golden capture workflow. | `feat/cosmyx-version` | carries copies of dark-default's 4 commits; imports `artifact_checks` (artifact-checks) and `mesa_win` (exec-smoke) at run time | [sheet](features/test-cosmyx-gui-goldens.md) |
| 25 | `feat/cosmyx-cloud-server` | #109 | CosmoCloud defaults, stealth on until the user opts out, custom orca-cloud Preferences panel. | `feat/cosmyx-stealth-mode` | rewrites stealth's `AppConfig.cpp` line; needs product-name's 4 cloud URL rows; `AppConfig.cpp` also hooked by dark-default | [sheet](features/feat-cosmyx-cloud-server.md) |
| 26 | `feat/cosmyx-plugin-signing` | #112 | CosmoCloud plugin package signature check (Ed25519 through OpenSSL) before install or update; pinned `PRODUCTION_KEYS` empty until the production key is provided (every Cosmyx-server install refused with `no_pinned_key` until then); `server_kind()` canonical-or-refuse address rule shared by Preferences and the trust check; per-server key pin or unverified opt-in in Preferences; `.cosmyx_package.json` record and anti-rollback; `package_gate()` latch keeps the check on once the app was seen; entry package name guard (CosmoCloud 0077). Upstream hooks: 22 lines in 7 files. `crypt32` linked into `cosmyx_tests` on WIN32. Decision 0204. | `feat/cosmyx-cloud-server` | changelog line under cloud-server's T18 slot (no own slot); edits decision 0203 | [sheet](features/feat-cosmyx-plugin-signing.md) |
| 27 | `ci/cosmyx-flatpak-off` | #113 | One added `if: ${{ vars.COSMYX_FLATPAK == 'true' }} # Cosmyx:` line on the `flatpak` job of `build_flatpak.yml`: the Flatpak leg and its unit tests are skipped unless the repository variable is `true`. Decision 0213, slot T19. | `chore/cosmyx-foundation` | product-name's `flatpak` package-name step and the foundation's flatpak test fixes live in the same file | [sheet](features/ci-cosmyx-flatpak-off.md) |
| 28 | `feat/cosmyx-raster-images` | #114 | 13 hand-recoloured raster overlays (8 Texture displacement tool tip pictures, 5 web images), `validated` by the user; kept-upstream list (6 bed plates, `Hex Tiles.png`, `setup_connection.gif`). Decision 0214, slot T11g. | `ci/cosmyx-branding-engine` | rows in `icons-n-z.json` and `web.json`, next to svg-candidates' rows | [sheet](features/feat-cosmyx-raster-images.md) |
| 29 | `ci/cosmyx-integrate` | #115 | Recipes `just cosmo-integrate [BASE]` (rebuild the integration of BASE, auto-resolve known conflicts, optional push and build) and `just cosmo-rebase-check TAG` (dry-run conflict map); branch list in `scripts/cosmyx/integrate/branches.json` (the machine list), a row not on the remote yet is skipped with a warning. One integration branch per base: `DEV` gives `ci/cosmyx-integration` in `.worktrees/integration`, any other base gives `integration/<BASE>` in `.worktrees/integration-<BASE>`. On a non-`DEV` base each branch's own commits are first replayed onto BASE as local `rebase/<BASE>/<branch>` branches (`cherry-pick -x`, never pushed), then merged `--no-ff`; an unknown conflict reuses an earlier hand resolution of the same original commit (found by its `-x` line), otherwise the run stops with the cherry-pick in progress. `--push` also pushes `cosmyx-ci/<BASE>` at the base commit; `--build` opens (or reuses) a never-merged draft PR head = integration branch, base = `cosmyx-ci/<BASE>`, built by "Cosmyx dev build"; `--os linux,windows,macos-arm64,macos-x86_64` sets its `build:*` labels. Decision 0215 (amended), slot T20. | `chore/cosmyx-foundation` | one `import?` line in the foundation-owned justfile; the PR build needs dev-build's `cosmyx-dev-build.yml` in the integration tree | none |
| 30 | `ci/cosmyx-mac-retry` | #116 | New `cosmyx-mac-retry.yml` (`workflow_run` on "Build all" and "Cosmyx dev build" completed) and `scripts/cosmyx/ci/mac_retry.py`: reruns the failed jobs when a macOS job carries the "was not acquired by Runner of type hosted" annotation, after a 15-minute wait, up to attempt 5; concurrency per workflow and head sha, never cancelled. No upstream file touched. `workflow_run` fires only from the default branch: inert until merged into `DEV`. Decision 0217 (amended), slot T22. | `chore/cosmyx-foundation` | watches dev-build's workflow by its name | [sheet](features/ci-cosmyx-mac-retry.md) |
| 31 | `ci/cosmyx-dev-build` | #119 | New "Cosmyx dev build" workflow `cosmyx-dev-build.yml` (pull request into `cosmyx-ci/**`, or `workflow_dispatch`) and `scripts/cosmyx/ci/dev_build.py`: builds an integration tree on any base on the OSes the `build:*` PR labels pick (none: Linux, Windows, macOS arm64), runs their unit tests, ships a `<product>_Mac_<arch>_<ver>` DMG per macOS arch. `build_all.yml` stays the release validation build. No upstream file touched. Decision 0218 (supersedes 0216's `build_all.yml` hook), slot T23. | `chore/cosmyx-foundation` | calls the base's own `build_check_cache.yml`, `build_orca.yml`, `unit_tests.yml`; reads product-name's packages table when present | [sheet](features/ci-cosmyx-dev-build.md) |

For a stacked child, "Parent" is the branch it is rebased onto; everything under the parent comes with it.
Every branch whose parent is `DEV` is rebased onto the rebased foundation (step 4 of `SKILL.md`).

## The foundation commits

PR #86 is not in `DEV`, so every branch carries the foundation commits `6cbd27d0fc` to `39c40f609f` (six
commits, same shas everywhere). `ci/cosmyx-artifact-checks`, `ci/cosmyx-macos-signing` and
`ci/cosmyx-exec-smoke` also carry `92830e0a8b`. The foundation tip has three more: `92830e0a8b`,
`41b887876e`, `be423c6998`. Consequences:

- Old base of a `DEV`-parented branch = `git merge-base origin/<branch> origin/chore/cosmyx-foundation`
  (`39c40f609f`, or `92830e0a8b` for artifact-checks). The replay then holds only the feature's own commits.
- After the rebase, each branch sits on the full rebased foundation: it gains the later foundation commits
  (the `goldens.just` and `macos-signing.just` imports in the justfile, the flatpak fixes). That is wanted.
- Foundation files carried in older variants by children (`test_foundation.py` at 190-198 lines vs 230 on the
  foundation tip) are resolved to the foundation version plus the child's own slot additions.

## Implicit dependencies (not visible in the parent chain)

| Who | Needs | Why | Effect if missing |
|-----|-------|-----|-------------------|
| `test/cosmyx-gui-goldens` | `ci/cosmyx-artifact-checks`, `ci/cosmyx-exec-smoke` | `scripts/cosmyx/gui_goldens/cli.py` imports `artifact_checks` (`slice`, `inventory`, `mesa_win.fetch` / `run_env`) at run time | slice check reports "not available", Windows Mesa step cannot run; build is fine |
| `test/cosmyx-gui-goldens` | `feat/cosmyx-dark-default` | carries byte-identical copies of its 4 commits (`ColorModeDefault`, `ColorMode`, hooks, `test_color_mode.cpp`, decisions 0136-0139, the T11f changelog line) | none; merge dark-default first, the copies merge as no-ops. Resolve their conflicts identically (rerere). Do not restack goldens on dark-default without the user's say. |
| `feat/cosmyx-cloud-server` | `feat/cosmyx-product-name` | 4 cloud URL patch rows (5 sites) in `cosmyx-src/branding/product-name/patches.json` point `cloud.orcaslicer.com` fallbacks at `orca-cloud.cosmyx3d.fr` (decision 0201) | a web pane reset loads the upstream cloud |
| `feat/cosmyx-plugin-signing` | `feat/cosmyx-cloud-server` (parent) | extends `logic/CloudServer.*` (`server_kind()`, `active_api_url()`) and `CloudServerPrefs.cpp` (signing key rows); its changelog line sits under T18 | none: stacked, cannot be merged alone |
| `ci/cosmyx-integrate` (`--build`) | `ci/cosmyx-dev-build` | the draft build PR targets `cosmyx-ci/<BASE>`; "Cosmyx dev build" only runs on it if the integration tree carries `cosmyx-dev-build.yml` (a `pull_request` run reads the workflow from the merge commit) | the draft PR opens but no build starts |
| macOS runner reruns | `ci/cosmyx-mac-retry` merged into `DEV` | `workflow_run` only fires from the default branch's copy of the workflow | until then, rerun starved macOS jobs by hand (step 8 of `SKILL.md`) |
| `feat/cosmyx-cloud-server` | `feat/cosmyx-dark-default` | both hook `src/libslic3r/AppConfig.cpp`; cloud's include goes after `#include "AppConfig.hpp"` to stay clear of dark's line 2 | textual conflict in the include block; hook-count test (fixed in `ed15f92456`) |
| `src/libslic3r/AppConfig.cpp` | stealth-mode, cloud-server, dark-default | stealth adds `return true;` as the first line of `get_stealth_mode()`, cloud-server replaces it with `return Cosmyx::stealth_mode(*this);` and adds an include after `AppConfig.hpp`; dark adds an include on line 2 and a call in `set_defaults()` | integration total: 4 `Cosmyx` lines; final getter line is cloud-server's |
| `src/slic3r/GUI/GUI_App.cpp` | version, dark-default, goldens, install-paths, cloud-server | include block lines 2-4 = version, ColorMode, GoldenDriver (in that order); install-paths includes after `Downloader.hpp`; cloud-server after `OrcaCloudServiceAgent.hpp`; product-name patches `SetAppDisplayName` at build time only | integration total: 12 `Cosmyx` lines (version 2, dark 2, goldens 2, install-paths 4, cloud 2) |
| `.github/workflows/build_orca.yml` | translations, version, windows-signing, macos-signing | four independent step blocks tagged `# Cosmyx`; wiring tests select steps by name | keep every block; a test that counts all `# Cosmyx` steps is a bug (`a2fbaba0fa`) |
| `CMakeLists.txt` (top) CPack block | install-paths, windows-signing (upstream include), product-name (build time) | `Packaging.cmake` is included after every upstream `CPACK_*`, appends to `CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS`, defaults `CPACK_NSIS_DISPLAY_NAME` only if undefined | never `set` over the signing include |
| `ci/cosmyx-artifact-checks`, `ci/cosmyx-exec-smoke` | models, version, translations | read `cosmyx_cube.3mf`, `CosmyxVersion.hpp`, `localization/cosmyx/` from the built commit | the check is skipped with a message |
| `feat/cosmyx-colours` | dark-default | contrast and the `BitmapCache.cpp` dark-map snippet assume dark mode is forced | visual only |
| `feat/cht-nozzle`, `feat/ironing-temperature`, `feat/cosmyx-models`, `feat/cosmyx-cloud-server` | translations | their `_L()` strings are extracted into `localization/cosmyx/<feature>/` | labels show in English |
| Every Cosmyx libslic3r file | ironing-temperature's link-closure test | a file defining a `PrintConfigDef` extension must not include GCode headers | `generate_system_cache` fails to link on Linux (`nsvg*` undefined) |

## Integration merge order

`integration/<tag>` starts at `refs/tags/upstream/<tag>` and merges `rebase/<tag>/<branch>` with `--no-ff` in
the "#" order of the table:

1. foundation, 2. upstream-sync, 3. bed-temp-off, 4. cht-nozzle, 5. ironing-temperature, 6. toolchange-fan-order,
7. models, 8. version, 9. stealth-mode, 10. translations, 11. windows-signing, 12. logs, 13. dark-default,
14. branding-engine, 15. logos, 16. colours, 17. product-name, 18. svg-candidates, 19. translations-fill,
20. artifact-checks, 21. macos-signing, 22. exec-smoke, 23. install-paths, 24. gui-goldens, 25. cloud-server,
26. plugin-signing, 27. flatpak-off, 28. raster-images, 29. integrate, 30. mac-retry, 31. dev-build. The DEV integration also merges
`docs/cosmyx-rebase-skill` (#111) last (`integration_only` row). `ci/cosmyx-arm64-pr-builds` (#117) was dropped: superseded by
decision 0218 (see `conflits.md`).

`scripts/cosmyx/integrate/branches.json` (on `ci/cosmyx-integrate`) is the machine copy of this order, read by
`just cosmo-integrate` and `just cosmo-rebase-check`: a new branch is one new row in the table above and one row
there, in the same change.

Why these places: dark-default before goldens (duplicate commits become no-ops); product-name before
install-paths and cloud-server (display name and URL rows); artifact-checks and exec-smoke before goldens
(runtime imports); stealth-mode and dark-default before cloud-server (`AppConfig.cpp`); plugin-signing right after its parent
cloud-server; product-name before macos-signing (its `mac-app` step must come first in `build_orca.yml`). The DEV-based
`origin/ci/cosmyx-integration` branch uses nearly the same order and is a reference for a known-good combined
tree; never push to it from this skill.

## Shared files and how to resolve them

| File | Who touches it | Rule |
|------|----------------|------|
| `CHANGELOG.md` | every branch | Each branch owns one slot marker `<!-- cosmyx-slot: Tn -->` and writes directly under it. Keep both sides' lines, never move or delete a marker, keep blank-line separation. T8 holds two lines: translations-fill's line above translations'. Goldens also carries dark-default's T11f line (identical). Slots: T0 foundation, T1 bed, T2 cht, T3 ironing, T4 fan, T5 models, T6 version, T7 stealth, T8 translations + fill, T9 windows-signing, T10 sync, T11a engine, T11b logos, T11c colours, T11d svg-candidates, T11e product-name, T11f dark-default, T11g raster-images, T12 logs, T13 artifact-checks, T15 macos-signing, T16 goldens, T16a exec-smoke, T17 install-paths, T18 cloud-server + plugin-signing (two lines), T19 flatpak-off, T20 integrate (repo area), T22 mac-retry, T23 dev-build (`CI-release`). T21 was arm64-pr-builds (dropped). GUI order in the file: ..., T11f, T16, T18, T11g. |
| `wiki/decisions/NNNN-*.md` | every branch | Numbers are unique per feature range; never renumber. Ranges: 0001-0005 foundation, 0010-0019 bed, 0020-0029 cht, 0030-0039 ironing, 0040-0049 fan, 0050-0059 models, 0060-0064 version, 0070-0073 stealth, 0080-0088 translations, 0090-0099 windows-signing, 0100-0105 sync, 0110-0111 logs, 0120-0123 engine, 0124-0126 logos, 0127-0130 colours, 0131 svg-candidates, 0132-0135 product-name, 0136-0139 dark-default (copied by goldens), 0140-0149 artifact-checks, 0150-0159 macos-signing, 0160-0161 exec-smoke, 0162-0179 goldens, 0180-0185 install-paths, 0200-0203 cloud-server, 0204 plugin-signing, 0210-0212 product-name (package names), 0213 flatpak-off, 0214 raster-images, 0215 integrate, 0216 arm64-pr-builds (dropped branch; its hook superseded by 0218), 0217 mac-retry, 0218 dev-build. Edits to someone else's decision: 0003 slot list (logs, install-paths, goldens, macos-signing, exec-smoke, cloud-server, flatpak-off, raster-images, integrate, mac-retry, dev-build: union of slots), 0123 (colours: hex rule), 0070/0071 (cloud-server marks superseded), 0146 (macos-signing, exec-smoke), 0203 (plugin-signing), 0132-0134 (product-name, package names). Keep every edit. Check with `just decisions`. |
| `scripts/cosmyx/tests/test_foundation.py` | foundation; slot additions by logs (T12), install-paths (T17), goldens (T16), cloud-server (T18), macos-signing (T15), exec-smoke (T16a), raster-images (T11g), flatpak-off (T19), integrate (T20), mac-retry (T22), dev-build (T23) | Resolved automatically by `just cosmo-integrate`; only check the result.  Take the foundation tip's file, then add each branch's own slot to `SLOTS_BY_AREA` (union). Sibling branches (for example logs and install-paths, both on the foundation) cannot carry each other's slot, so the integration merge always conflicts here and in decision 0003: resolve that conflict in the merge itself by union (this is the one integration conflict not fixed in a feature branch; `rerere` replays it). The flatpak tests point at the file that really holds the flatpak lines on the target (see `conflits.md`). |
| `justfile` | foundation only | Branches never edit it: recipes are loaded by `import?` lines. On conflict take the foundation version. |
| `scripts/cosmyx/run_script_tests.py`, `scripts/cosmyx/decisions.py` | foundation only | Take the foundation version. |
| `.github/workflows/cosmyx-checks.yml` | foundation; `paths:` lists widened over time | Take the foundation tip; add a path a branch needs (union). |
| `.github/workflows/build_all.yml` | flatpak-off and the foundation's flatpak fixes on tags whose `flatpak:` job is still in this file | No Cosmyx hook on `DEV` (the release validation build stays upstream's). The file is CRLF upstream: an added line keeps CRLF. |
| `tests/CMakeLists.txt`, `src/libslic3r/CMakeLists.txt`, `src/slic3r/CMakeLists.txt`, `PrintConfig.cpp` line 2 and ctor call, `GCode.cpp` line 2 | foundation (identical copies in every branch) | One copy of each hook line. `PrintConfig.cpp` also has cht's `s_keys_map_NozzleType` row and ironing's `validate()` hook, `GCode.cpp` ironing's four hooks: different regions, keep all. |
| `src/libslic3r/Cosmyx/{BedTemperatureOff,ChtNozzle,IroningTemperature}.*` | foundation stubs; real code in bed, cht, ironing | Keep the feature's real file, never the stub. |
| `src/libslic3r/Cosmyx/GCodeHooks.hpp`, `ConfigDefExtensions.hpp` | foundation; bed and ironing add includes, ironing declares `validate_option_ranges` | Union of the lines. |
| `src/slic3r/GUI/GUI_App.cpp`, `src/libslic3r/AppConfig.cpp` | see "Implicit dependencies" | Keep every hook; include order version, ColorMode, GoldenDriver at lines 2-4. |
| `.github/workflows/build_orca.yml` | translations, version, windows-signing, macos-signing, product-name (package-name steps `mac-app`, `mac-upload`, `windows`, `linux`) | Keep each `# Cosmyx` block at its own anchor. After "Create DMG without notary" the order is product-name's `mac-app` step FIRST, then macos-signing's "Cosmyx sign and notarize macOS" (the signing re-signs and rebuilds the DMG under the renamed app's name). |
| `.github/workflows/build_flatpak.yml` | foundation (flatpak test fixes), product-name (`flatpak` package-name step before "Upload artifacts Flatpak"), flatpak-off (`if:` line on the `flatpak` job) | Different anchors; keep all. |
| `.github/actions/cosmyx-prepare/action.yml` | translations (creates), engine (adds) | Order: `safe.directory` first, graft, branding, `hide` last. |
| `scripts/cosmyx/worktree_clean.py` | translations, reused by engine | Translations owns it. |
| `cosmyx-src/branding/manifest/*.json`, `wiki/cosmyx/branding-assets/*.md` | engine, logos, svg-candidates, raster-images | Never merge by hand: take one side, then `just brand-sync` and `just brand-table` on the unbranded tree, commit the result in the branch that owns the rows (in the integration: in the merge commit). `brand-sync` keeps a row's status while its `override_sha256` is unchanged: count the `validated` rows before and after (571 = 34 logos + 524 svg + 13 rasters). |
| `cosmyx-src/branding/overlay/` | logos, svg-candidates, raster-images | One owner per path (G2 fails on an orphan overlay file). |
| `wiki/cosmyx/branding.md` | engine, logos, colours, product-name, svg-candidates, dark-default | Each has its own section; keep all sections. |
| `scripts/cosmyx/branding/__init__.py`, `guards.py`, `branding_fixture.py`, `test_branding_apply.py` | engine; colours (`hex_is_skipped`), product-name (G8 plugin), logos (`manifest.refresh` in one test) | Union; the engine's single `copy_real_tree` helper stays. |
| `cosmyx-src/branding/colours.json` | colours; other branches add `allow_residue` rows | Keep rows sorted; regenerate tuple rows with `just brand-colour-literals`; never change a status. |
| `cosmyx-src/branding/product-name/patches.json` | product-name (includes cloud-server's 4 URL rows) | Keep the URL rows. |
| `localization/cosmyx/<feature>/*` | translations, translations-fill, and feature branches via `just i18n-extract` | Keep the translated side; never edit a `msgid`; a new or changed msgid goes to a per-language translator, not into this rebase. |
| `scripts/cosmyx/artifact_checks/*`, `data/expectations.json`, `.github/workflows/cosmyx-artifact-checks.yml`, `wiki/cosmyx/artifact-checks.md`, `test_breaker_info_plist.py`, `test_breaker_smoke_output_encoding.py` | artifact-checks, macos-signing, exec-smoke (linear stack) | Resolved inside the stack: child adapts to rebased parent. |
| `.github/cosmyx/workflow-policy.json` | upstream-sync | Edit only the JSON lists when the target's scheduled workflows differ. |
| `src/slic3r/GUI/Cosmyx/logic/GuidePolicy.hpp`, `tests/cosmyx/test_cosmyx_stealth.cpp` | stealth-mode, cloud-server | Cloud-server's version wins (it is the child). |
| `tests/libslic3r/test_utils.cpp`, `src/libslic3r/utils.cpp` | install-paths | Two-line hooks (decision 0185); logs relies on `g_log_sink` in `utils.cpp` without editing it. |
| `tests/cosmyx/CMakeLists.txt`, `Cosmyx.cmake` | foundation (globs); plugin-signing (link line) | No branch edits them to add files. Plugin-signing adds `OpenSSL::Crypto` to the `cosmyx_tests` link line and `crypt32` on WIN32: keep. |

## State at the last pass

DEV integration rebuild, 2026-11-24: no upstream tag beyond `v2.5.2`, so no rebase pass; `ci/cosmyx-integration` was
rebuilt from `origin/DEV` (`3838002bc8`) with the `origin` tip of every open PR (rows 1-28 plus #111), see `conflits.md`.
Tips used: windows-signing `43e711ef86`, artifact-checks `53df024c32`, macos-signing `7d0ae8d5b4`, exec-smoke
`526fc8002e`, logos `98cebb719f`, product-name `c09dd71e36`, svg-candidates `9a9034d1a9`, gui-goldens `2367b858cd`,
plugin-signing `3a16c1e3c3`, flatpak-off `e2e6aba26f`, raster-images `4fbffcfa64`; every other branch as in the table
below. The rows 26-28 have no `rebase/v2.5.2` copy yet.

Dry run onto `v2.5.2` (`f92a7c065c`), 2026-11-23. `origin` tips the copies were made from (compare with them to see
what moved before the next pass), and the copy tips `rebase/v2.5.2/<branch>`. Every branch sits on `DEV` `3838002bc8`. Since
the v2.5.1 pass only `feat/cosmyx-translations` changed (`04f9955f54` added); the branding engine, logos, colours,
product-name, svg-candidates and translations-fill were restacked onto it with the same patches.

| # | Branch | origin tip | Copy tip | Commits added by the pass |
|---|--------|------------|----------|---------------------------|
| 1 | `chore/cosmyx-foundation` | `be423c6998` | `cef12aa526` | none |
| 2 | `ci/cosmyx-upstream-sync` | `4601573750` | `e17d1cbbe6` | none |
| 3 | `feat/bed-temp-off` | `de8058dc33` | `91484e311a` | none |
| 4 | `feat/cht-nozzle` | `08d8d62f96` | `d91077eb34` | none |
| 5 | `feat/ironing-temperature` | `685b434cb4` | `03ceaac55c` | none |
| 6 | `fix/toolchange-fan-order` | `e9ab15ae0f` | `e80ff81c91` | none |
| 7 | `feat/cosmyx-models` | `662b5d79fa` | `4fa0d6e386` | none |
| 8 | `feat/cosmyx-version` | `c34bce56ac` | `7f2e49e3d5` | none |
| 9 | `feat/cosmyx-stealth-mode` | `aa48e1b4c0` | `2301b058a0` | none |
| 10 | `feat/cosmyx-translations` | `04f9955f54` | `76cb75b5b4` | none |
| 11 | `feat/cosmyx-windows-signing` | `a2fbaba0fa` | `a88a79d944` | none |
| 12 | `feat/cosmyx-logs` | `1a54759bd4` | `bc645d0bd3` | none |
| 13 | `feat/cosmyx-dark-default` | `b93fce0559` | `0d565acb09` | none |
| 14 | `ci/cosmyx-branding-engine` | `e3c74df8d3` | `718f663275` | `718f663275` |
| 15 | `feat/cosmyx-logos` | `c16c57f6dd` | `b49d45db81` | none |
| 16 | `feat/cosmyx-colours` | `3ba961954b` | `33fbc1c012` | `33fbc1c012` |
| 17 | `feat/cosmyx-product-name` | `cb31da2577` | `e1e7a173f0` | `e1e7a173f0` |
| 18 | `feat/cosmyx-svg-candidates` | `e5e44314e0` | `715c60a6f7` | none |
| 19 | `feat/cosmyx-translations-fill` | `127f5bb985` | `734b073410` | none |
| 20 | `ci/cosmyx-artifact-checks` | `0f40efe642` | `8799fe174f` | none |
| 21 | `ci/cosmyx-macos-signing` | `e6524bdeba` | `1944146a11` | none |
| 22 | `ci/cosmyx-exec-smoke` | `fcf2a4cc91` | `7801e15059` | none |
| 23 | `feat/cosmyx-install-paths` | `28aa25e538` | `950ee9d4e4` | none |
| 24 | `test/cosmyx-gui-goldens` | `6ee87da92f` | `da81bbfea6` | `da81bbfea6` |
| 25 | `feat/cosmyx-cloud-server` | `ed15f92456` | `f9a6bd001f` | none |

`integration/v2.5.2` = `b94fa72efb`, build run 45136685686.
