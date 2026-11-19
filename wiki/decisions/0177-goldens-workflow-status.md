# 0177. The goldens workflow and its required status

## Status

Accepted.

## Context

The user wants the status required on DEV and release/* as soon as it has
posted once, so it must post on every build that can merge.

## Decision

- `.github/workflows/cosmyx-gui-goldens.yml` runs on every completed
  "Build all" run (`workflow_run`), on dispatch (`run_id`, `mode`,
  `stability`) and weekly on the latest successful DEV build.
- The harness and the Docker image come from the workflow's own commit; the
  built commit only gives `version.inc` and `tests/cosmyx/gui/` (script,
  tolerances, goldens). Builds from forks are never run (decision 0141).
- Jobs: resolve (plan, pending status), capture per OS (Docker on
  ubuntu-24.04, macos-15, windows-2025 at 1920x1080 and 96 DPI), status.
- The commit status `cosmyx/gui-goldens` is posted on every compare run:
  success only when every OS matched; failure when a build failed, came from a
  fork, lacked an OS artifact or did not match. On `MIXED` it only reports
  (success with "report only").

## Consequences

- Branch protection on DEV and release/* can require `cosmyx/gui-goldens`
  once it has posted (a repository setting, not part of this change).
