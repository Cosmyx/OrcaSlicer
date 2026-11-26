# ci/cosmyx-dev-build (PR #119)

## Purpose

Integration trees (every Cosmyx branch merged on a base) need a build shaped for development: only the OSes the change
needs, the same behaviour on `DEV` and on an older upstream tag, and no edit to an upstream workflow. This branch adds
the "Cosmyx dev build" workflow, run by the never-merged draft PR that `just cosmo-integrate --build` opens into
`cosmyx-ci/<BASE>`. `build_all.yml` stays untouched and remains the release validation build (full matrix, universal
macOS app, Flatpak). Decision 0218 (supersedes the `build_all.yml` hook of decision 0216 and its branch
`ci/cosmyx-arm64-pr-builds`, dropped), changelog slot T23 (`### CI-release`).

## Parent and dependencies

- Parent: `chore/cosmyx-foundation` (PR #86). Range: `48911cb437` (workflow, script, test, decision, slot), `0b12ff3d84`
  (changelog PR link).
- Calls the base's own reusable workflows `build_check_cache.yml`, `build_orca.yml` (through it) and `unit_tests.yml`
  with the inputs `build_all.yml` passes; those inputs exist on `DEV` and on `v2.5.2`. The Cosmyx hooks the integration
  tree carries in `build_orca.yml` run as usual.
- Reads the product name from product-name's packages table when the tree has it (CosmoSlice otherwise), and the
  version through `scripts/cosmyx/cosmyx_version.py` when the tree has it (version branch).
- `ci/cosmyx-integrate` (`--build`, `--os`) opens or reuses the PRs this workflow builds and sets their `build:*` labels.
- `ci/cosmyx-mac-retry` watches its runs by the name "Cosmyx dev build".

## Changes

| File | Kind | What the change does |
|---|---|---|
| `.github/workflows/cosmyx-dev-build.yml` | CI (Cosmyx-owned) | "Cosmyx dev build". Triggers: `pull_request` into `cosmyx-ci/**` (opened, synchronize, reopened, labeled, unlabeled) and `workflow_dispatch` (checkboxes `linux`, `windows`, `macos-arm64` on, `macos-x86_64` off; the form shows only once the file is on `DEV`). Concurrency one run per PR or ref, newest cancels; a label event outside `build:` gets its own group and builds nothing. Jobs: `select`, Linux x86_64 and aarch64, Windows x64, macOS per chosen arch, `macOS DMG <arch>` (keeps the product DMG, repacks upstream's per-arch DMG, or packs the app bundle with upstream's `scripts/create_dmg.sh`), unit tests per built OS (none for macOS x86_64), test results. Left out: Windows build script tests, Linux slice check, universal macOS app, Flatpak. |
| `scripts/cosmyx/ci/dev_build.py` | Cosmyx-owned | `select` (labels `build:linux`, `build:windows`, `build:macos-arm64`, `build:macos-x86_64`; none gives Linux, Windows, macOS arm64; an unknown `build:` label fails), `version`, `product`, `dmg_plan`. Standard library only. |
| `scripts/cosmyx/tests/test_dev_build.py` | test | `PullRequestSelectionTests`, `DispatchSelectionTests`, `OutputTests`, `VersionTests`, `DmgPlanTests`, `WorkflowTests` (trigger, checkboxes, concurrency, gating, reusable inputs exist in the called workflow, unit tests follow their build). |
| `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md` | foundation files | `T23` added to `CI-release`. |
| `wiki/decisions/0218-cosmyx-dev-build.md` | docs | Decision. |
| `CHANGELOG.md` | data | Line under `<!-- cosmyx-slot: T23 -->`. |

No upstream file is edited.

## Rebase risk zones

- Upstream renames or changes the inputs of `build_check_cache.yml`, `build_orca.yml` or `unit_tests.yml`:
  `WorkflowTests.test_reusable_inputs_exist_in_the_called_workflow` fails; follow the base's inputs.
- Upstream changes the macOS artifact names (per-arch DMG `OrcaSlicer_Mac_<arch>_<ver>`, bundle
  `OrcaSlicer_Mac_bundle_<arch>_<sha>`) or moves `scripts/create_dmg.sh`: adapt `dmg_plan` and the DMG job.
- Upstream renames macOS jobs inside `build_orca.yml`: mac-retry matches `macos` in the job name.
- Upstream changes the deps cache key logic (amd64's empty `arch` keeps the `linux-clang` key, as in `build_all.yml`).

## Intent to preserve

- No upstream workflow edited; `build_all.yml` is the release validation build.
- Same behaviour on every base; only the OSes asked for are built.
- Selection logic in the tested script, not inline shell.

## Verification

- `just test-scripts` (`test_dev_build.py`, slot checks); `just decisions`.
- On an integration: `just cosmo-integrate <BASE> --push --build --os ...` starts a "Cosmyx dev build" run on the draft
  PR with exactly those OSes, ending with one `<product>_Mac_<arch>_<ver>` DMG per built macOS arch.

## Known pitfalls

- The workflow runs only if the integration tree carries it (a `pull_request` run reads the workflow from the merge
  commit): dev-build must be in the merge order.
- `workflow_dispatch` shows no form until the file is on `DEV`; until then the PR labels choose the OSes.
- On `v2.5.2`, `build_check_cache.yml` finds no base build to wait for on a macOS deps cache miss and builds the deps
  itself (slow, not a failure).
- Never close the build PR while its run is going: `cancel_closed_pr_builds.yml` cancels it.
- Slot union: the integration merge conflicts with sibling slots in `CI-release` (T15, T16a, T19, T22); resolved by union.

## Shared files with other branches

- `CHANGELOG.md` (T23), `test_foundation.py`, decision 0003.
