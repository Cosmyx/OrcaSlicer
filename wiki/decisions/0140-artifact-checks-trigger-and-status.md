# 0140. Artifact checks run after "Build all" and post a commit status

## Status

Accepted.

## Context

`build_all.yml` and `build_orca.yml` are upstream files. Adding checks inside
them would conflict with every upstream merge. The checks need the finished
artifacts of every OS anyway, which only exist once the whole build is done.

## Decision

- `.github/workflows/cosmyx-artifact-checks.yml` runs on `workflow_run` of
  "Build all" (`completed`) and on `workflow_dispatch` with a `run_id` and a
  `strict` switch (default false). It never runs on the upstream repository.
- A cancelled or skipped build is not checked. Any other conclusion is
  checked; the required set (decision 0144) only applies to successful builds.
- The resolve job posts a `pending` commit status `cosmyx/artifact-checks` on
  the built commit; the last job posts `success` or `failure` with a link to
  the check run. The status can be made a required check in branch protection.
- One run per build run (`concurrency` by run id, never cancelled).

## Consequences

- `workflow_run` only fires from the copy of the workflow on the default
  branch (DEV): until it is merged, the checks are started by hand
  (`just artifact-checks <run id>`) or run locally.
- Removing it: delete the workflow, `scripts/cosmyx/artifact_checks/` and the
  recipes in `scripts/cosmyx/just/tests.just`; drop the status from branch
  protection if it was made required.
