# 0104. MIXED is merged without a working tree

## Status

Accepted.

## Context

The plan described the MIXED step as "check out DEV, `git merge --no-ff`".
OrcaSlicer is a large repository: a checkout costs time and disk on every run,
and a working tree adds states to clean up (merge in progress, abort).

## Decision

- The sync fetches `DEV`, `Orca-Upstream` and `MIXED` into a scratch bare
  repository and merges with `git merge-tree --write-tree --name-only`, which
  returns the merged tree or the list of conflicted files (git 2.38 or later,
  present on the GitHub runners).
- The commit is written with `git commit-tree` with the two parents and the
  `Cosmyx-Mixed` trailer, under the `github-actions[bot]` identity, then
  force-pushed. The result is the same commit a `git merge --no-ff` would give.
- Nothing is aborted on a conflict, because nothing was started.

## Consequences

- No checkout of the sources; the job needs git 2.38 or later.
- Going back to a checkout merge only touches the `merge_trees` function of
  `scripts/cosmyx/upstream_sync.py`.
