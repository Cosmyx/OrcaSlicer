# 0217. Builds whose macOS jobs got no hosted runner rerun by themselves

## Status

Accepted.

## Context

Hosted macOS runners are scarce. When GitHub cannot acquire one, it cancels the
macOS job of a "Build all" or "Cosmyx dev build" (decision 0218) run with
the annotation "The job was not acquired by
Runner of type hosted even after multiple attempts". The run then ends failed
or cancelled although the code is fine, and someone had to rerun the failed
jobs by hand, or with a local script, often several times.

A job can also be cancelled on purpose: by a user, or by a newer push through a
concurrency group. Those runs must not be restarted.

## Decision

- `.github/workflows/cosmyx-mac-retry.yml` runs on `workflow_run` for
  "Build all" and "Cosmyx dev build", `types: [completed]`, and its job only runs when the run
  concluded `failure` or `cancelled`. It is a new file: no upstream workflow is
  edited (decision 0002).
- The logic lives in `scripts/cosmyx/ci/mac_retry.py` (Python standard library,
  tested by `scripts/cosmyx/tests/test_mac_retry.py`), not in inline shell.
  `decide` lists the jobs of the run's latest attempt
  (`/actions/runs/{id}/jobs?filter=latest`), keeps the jobs whose name contains
  `macos` (any case) that ended `cancelled` or `failure`, and reruns only when
  one of them carries the runner acquisition annotation
  (`/check-runs/{job id}/annotations`, matched on "was not acquired by Runner
  of type hosted", any case). Every job that runs on macOS has `macos` in its
  name in both workflows: the reusable-workflow legs `build_macos_arch
  (<arch>) / ...` and `macOS arm64 / Unit Tests`, `Build macOS Universal`
  (Build all) and `macOS DMG <arch>` (dev build); no other job does. A failed conclusion is accepted next to
  cancelled because the annotation, not the conclusion, proves the cause.
- Retries stop once the run's attempt reaches `MAX` (default 5, repository
  variable `COSMYX_MAC_RETRY_MAX_ATTEMPTS`).
- Before rerunning, the job waits (default 900 seconds, repository variable
  `COSMYX_MAC_RETRY_WAIT_SECONDS`) with `sleep`, so a runner has a chance to
  free up. A Linux runner waiting costs nothing on a public repository.
- After the wait, `rerun` checks the run is still the same completed attempt
  (nobody reran it meanwhile) and then calls
  `POST /actions/runs/{id}/rerun-failed-jobs`, the API behind
  `gh run rerun <id> --failed`. Calling it from the script, instead of `gh`,
  keeps the check and the rerun in one tested place.
- Permissions are `actions: write` (rerun) and `checks: read` (annotations;
  every permission not listed is none).
- Concurrency group `cosmyx-mac-retry-<workflow id>-<head sha>` with
  `cancel-in-progress: false`: two triggers of the same workflow for the same
  commit never rerun twice (the second one finds the attempt changed and does
  nothing), and the two watched workflows building one commit never queue
  behind each other.
- Every outcome prints why it reruns or not in the job log.

`workflow_run` only fires from the copy of the workflow file on the default
branch (`DEV`). The workflow is inert on its feature branch and in its pull
request, and starts working once merged into `DEV`.

## Consequences

- A run starved of macOS runners is retried up to the limit without anyone
  watching it; each retry adds a few minutes of Linux runner time.
- A macOS job that keeps getting no runner stops being retried at attempt 5,
  and the run stays red for a human to look at.
- If GitHub rewords the annotation, the retry silently stops matching: the log
  says "no runner acquisition annotation", and the match string in
  `mac_retry.py` must be updated.
- Removing this decision means deleting the workflow, the script and its test.
