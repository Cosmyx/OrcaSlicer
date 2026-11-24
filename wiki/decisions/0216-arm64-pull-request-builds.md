# 0216. Integration builds run "Build all" in pull request mode

## Status

Accepted.

## Context

An integration branch (DEV or a release tag, plus every open Cosmyx branch)
was built by starting `build_all.yml` by hand (`workflow_dispatch`). Upstream
treats that like a push: macOS builds arm64 and x86_64, then a universal app
from both. Hosted macOS runners are scarce, so these runs kept failing or
waiting on macOS, while the x86_64 and universal legs bring nothing to an
integration check.

Upstream's pull request mode already does what an integration check needs:
macOS builds arm64 only, waits in the `macos-admission` queue of
`build_check_cache.yml` (one macOS runner at a time, yielding to push and
nightly builds), packs each arch as its own unsigned DMG and builds no
universal app. Windows builds x64 only; Linux builds x86_64 and aarch64. But
`build_all.yml` only runs for pull requests based on `main` or `release/*`,
and Cosmyx pull requests target DEV.

## Decision

- An integration of a base `<BASE>` (DEV or a tag such as `v2.5.2`) is built
  through a draft pull request that is never merged: its head is the
  integration branch, its base is a branch `cosmyx-ci/<BASE>` pushed at the
  exact base commit. The merge commit then has the integration's tree.
- The `pull_request.branches` list of `build_all.yml` gets one added line,
  `- 'cosmyx-ci/**'`, tagged `# Cosmyx:`. No upstream line is edited, and the
  push, schedule and manual triggers are unchanged. The file is committed with
  CRLF line endings upstream, and the added line keeps them.
- `scripts/cosmyx/tests/test_arm64_pr_builds.py` pins the line, the untouched
  triggers, the `paths:` filter, and the upstream pull request behaviour this
  decision relies on (arm64 only, no universal app).
- `cosmyx-checks.yml` lists `build_all.yml` in its `paths:` filters, next to
  the other upstream build workflows that carry Cosmyx hooks, so an upstream
  edit of the file reruns that test.

## What else such a pull request starts

Checked against the integration branch. Workflows that do not run:
`build_optional.yml`, `check_locale.yml`, `check_profiles.yml`,
`clang_tidy.yml` and `approve_pr_checks.yml` (their branch lists are `main`
and `release/*`), and `cosmyx-checks.yml` (DEV only). The ones that do:

- `cancel_closed_pr_builds.yml` (`pull_request_target: closed`, any base):
  closing the draft pull request cancels its unfinished "Build all" run. Close
  it only once the build is over.
- `pr-label-bot.yml` (`pull_request_target: opened, reopened`, any base): its
  job skips authors who are owners, members or collaborators, so it does
  nothing when the pull request is opened by the fork's maintainers.
- `pr-merge-bot.yml` (`pull_request_target: opened`, `resources/profiles/**`):
  every job requires `github.repository == 'OrcaSlicer/OrcaSlicer'`, so it is
  skipped.
- `shellcheck.yml` (`pull_request`, any base, `**.sh` and `scripts/linux.d/*`):
  runs only if the integration changes a shell script. Light (one Linux job).
- `cosmyx-artifact-checks.yml` and `cosmyx-gui-goldens.yml` run after "Build
  all" completes, as for any build. The goldens use a macOS runner too.

None of them is harmful. `pull_request_target` workflows run from the base
branch, that is the base commit's copy.

## The `paths:` filter

The `pull_request` trigger keeps upstream's `paths:` filter, matched against
the diff between the base and the integration. An integration always changes
`src/**`, `CMakeLists.txt`, `cmake/**` and `.github/workflows/build_*.yml`, so
it matches. GitHub only looks at the first 300 changed files: the integration
diff on DEV has about 1100, and the first 300 (in path order) still hold five
matching files, `.github/workflows/build_flatpak.yml` and `build_orca.yml`
first.

## The macOS artifact

In pull request mode the "Create DMG `<arch>` without notary" step of
`build_orca.yml` packs `build/arm64/OrcaSlicer/OrcaSlicer.app` into
`OrcaSlicer_Mac_arm64_<ver>.dmg` (volume "OrcaSlicer") and uploads it as
`OrcaSlicer_Mac_arm64_<ver>`. Upstream sets `ver=PR-<number>`, but the Cosmyx
step "Name the build after the Cosmyx version" (decision 0062) then writes
`ver=<display version>_<short hash>` from the pull request head, so the name
carries the Cosmyx version of the integration tip.

The CosmoSlice renaming (decision 0210, `scripts/cosmyx/package_names.py`)
only handles the universal bundle (`build/universal/OrcaSlicer`): on a
per-arch leg its `mac-app` and `mac-upload` stages do nothing. The pull
request mode DMG therefore still says OrcaSlicer, in its file, artifact,
volume and app names. That is fixed on the branch that owns the renaming
(`feat/cosmyx-product-name`), not here.

## Consequences

- An integration build needs one macOS arm64 runner instead of two plus a
  combine job, and queues for it rather than failing.
- No universal or x86_64 macOS app and no Windows arm64 build come out of an
  integration build; signed release builds still come from DEV and `release/*`
  pushes, which this does not touch.
- A pull request restores deps caches of its base and of the default branch
  (DEV), not of the integration branch, and saves its own under the pull
  request's merge ref. Reusing one draft pull request per base keeps those
  caches across integration rebuilds.
- Removing this decision means deleting the added line; integration builds
  then go back to a manual run.
