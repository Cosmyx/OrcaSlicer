# ci/cosmyx-mac-retry (PR #116)

## Purpose

When GitHub cannot acquire a hosted macOS runner it cancels the macOS job of a "Build all" run ("The job was not acquired
by Runner of type hosted even after multiple attempts"), and someone had to rerun the failed jobs by hand. This branch
reruns them by itself. Decision 0217, changelog slot T22 (`### CI-release`).

## Parent and dependencies

- Parent: `chore/cosmyx-foundation` (PR #86). Range: `5ae17330d7` (workflow, script, test, decision, slot), `b9a10ccda1`
  (changelog PR link).
- `workflow_run` only fires from the copy of the workflow on the default branch: the workflow is inert on its branch,
  in its PR and in an integration branch, and starts working once merged into `DEV`.

## Changes

| File | Kind | What the change does |
|---|---|---|
| `.github/workflows/cosmyx-mac-retry.yml` | CI (Cosmyx-owned) | `workflow_run` on "Build all" `completed`; job runs on conclusion `failure` or `cancelled`; `decide`, wait (`COSMYX_MAC_RETRY_WAIT_SECONDS`, default 900), `rerun`; max attempt `COSMYX_MAC_RETRY_MAX_ATTEMPTS` (default 5); permissions `actions: write`, `checks: read`; concurrency per head sha, never cancelled. |
| `scripts/cosmyx/ci/mac_retry.py` | Cosmyx-owned | `decide`: macOS jobs of the latest attempt that ended cancelled or failed and carry the runner acquisition annotation. `rerun`: checks the attempt did not change, then `POST /actions/runs/{id}/rerun-failed-jobs`. Standard library only. |
| `scripts/cosmyx/tests/test_mac_retry.py` | test | `DecideTests` (annotation match any case, non-macOS or unannotated job left alone, attempt limit, latest attempt on every page), `RerunTests` (rerun meanwhile or still running left alone), `WorkflowTests` (trigger, watched name exists, minimal permissions, concurrency, step order, defaults). |
| `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md` | foundation files | `T22` added to `CI-release`. |
| `wiki/decisions/0217-macos-runner-retry.md` | docs | Decision. |
| `CHANGELOG.md` | data | Line under `<!-- cosmyx-slot: T22 -->`. |

No upstream file is edited.

## Rebase risk zones

- The trigger names the workflow "Build all": if upstream renames `build_all.yml`'s `name:`, update `workflows:`.
- If GitHub rewords the annotation, `decide` stops matching ("no runner acquisition annotation" in the log): update the
  match string in `mac_retry.py`.
- Job selection is by `macos` in the job name (any case): check after upstream renames the macOS jobs.

## Intent to preserve

- Only runs starved of a runner are retried; runs cancelled by a user or a newer push are left alone.
- Logic in the tested script, not inline shell.

## Verification

- `just test-scripts` (`test_mac_retry.py`, slot checks); `just decisions`.
- Only after merge into `DEV`: a run with a starved macOS job shows a "Cosmyx macOS runner retry" run that reruns it.

## Known pitfalls

- Testing it on the branch or the integration does nothing (`workflow_run` from the default branch only).
- Slot union: the integration merge conflicts with sibling slots in `CI-release` (T15, T16a, T19, T21); resolve by union.

## Shared files with other branches

- `CHANGELOG.md` (T22), `test_foundation.py`, decision 0003.
