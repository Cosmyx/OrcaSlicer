# ci/cosmyx-arm64-pr-builds (PR #117)

## Purpose

Integration builds were started with `workflow_dispatch`, which upstream treats like a push: macOS builds arm64 and
x86_64 plus a universal app, and kept failing or waiting for scarce macOS runners. Upstream's pull request mode builds
macOS arm64 only, queues in `macos-admission` and packs an arm64 DMG. This branch lets `build_all.yml` run on pull
requests into `cosmyx-ci/**`, so an integration is built through a never-merged draft PR (head = integration branch,
base = `cosmyx-ci/<BASE>` at the base commit). Decision 0216, changelog slot T21 (`### CI-release`, flagged **Changed**).

## Parent and dependencies

- Parent: `chore/cosmyx-foundation` (PR #86). Range: `feaff1ef20` (hook, test, decision, slot), `737c3c5ddd` (changelog PR
  link), `f425b0b7ac` (`cosmyx-checks.yml` paths).
- `ci/cosmyx-integrate` (`--build`) opens and reuses the draft PRs this line lets build.

## Changes

| File | Kind | What the change does |
|---|---|---|
| `.github/workflows/build_all.yml` | upstream hook (1 line) | `     - 'cosmyx-ci/**' # Cosmyx: integration builds run in pull request mode (decision 0216)` added after `- release/*` in `on.pull_request.branches`. The file is CRLF upstream; the line keeps CRLF. Push, schedule and manual triggers and the `paths:` filter unchanged. |
| `.github/workflows/cosmyx-checks.yml` | foundation file | `.github/workflows/build_all.yml` added to both `paths:` lists, so an upstream edit reruns the test. |
| `scripts/cosmyx/tests/test_arm64_pr_builds.py` | test | `Arm64PullRequestBuildTests` (line present, one tagged line, `paths:` kept, push and manual triggers unchanged, PR mode builds macOS arm64 only), `CosmyxChecksTriggerTests`. |
| `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md` | foundation files | `T21` added to `CI-release`. |
| `wiki/decisions/0216-arm64-pull-request-builds.md` | docs | Decision (what else such a PR starts, `paths:` filter, macOS artifact). |
| `CHANGELOG.md` | data | Line under `<!-- cosmyx-slot: T21 -->`. |

## Rebase risk zones

- If upstream edits the `pull_request.branches` list of `build_all.yml`, keep their list and re-add the one tagged line.
- If upstream changes what pull request mode builds (arm64 only, no universal), `test_pull_request_mode_builds_macos_arm64_only`
  fails: reread decision 0216 before adapting.
- On `v2.5.1` / `v2.5.2` the `flatpak:` job also sits in `build_all.yml`, where flatpak-off adds its `if:` line: different
  anchor, keep both.

## Intent to preserve

- One added, tagged line; no upstream line edited.
- Closing a build PR cancels its run (`cancel_closed_pr_builds.yml`): never close one while it builds.

## Verification

- `just test-scripts` (`test_arm64_pr_builds.py`, slot checks); `just decisions`.
- A draft PR into `cosmyx-ci/<BASE>` starts "Build all" with only the macOS arm64 leg.

## Known pitfalls

- A `pull_request` run reads `build_all.yml` from the merge commit: the integration tree itself must carry the line.
- Slot union: the integration merge conflicts with sibling slots in `CI-release` (T15, T16a, T19, T22); resolve by union.
- Decision 0216 says the per-arch DMG still says OrcaSlicer; product-name fixed that in `ea648096aa`.

## Shared files with other branches

- `.github/workflows/build_all.yml`: flatpak-off on tags without `build_flatpak.yml`.
- `.github/workflows/cosmyx-checks.yml`: foundation (paths union).
- `CHANGELOG.md` (T21), `test_foundation.py`, decision 0003.
