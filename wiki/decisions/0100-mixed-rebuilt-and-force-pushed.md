# 0100. MIXED is rebuilt from scratch and force-pushed

## Status

Accepted.

## Context

The fork must merge upstream with zero conflicts. A guard branch has to show,
soon after upstream moves, whether the current `DEV` still merges cleanly and
still builds. A branch that accumulates merges would hide the state of the
current pair of tips behind older merges.

## Decision

- `MIXED` is recomputed on every run as one merge commit of the current `DEV`
  tip (first parent) and the current `Orca-Upstream` tip (second parent), and
  force-pushed. It always has two parents, even when `Orca-Upstream` is
  already contained in `DEV`.
- The commit message ends with `Cosmyx-Mixed: base=<sha> upstream=<sha>`.
  When the `MIXED` tip already records the same pair, the run pushes nothing
  and starts no build.
- A conflict fails the run with exit code 2, lists the files in the job summary
  and as error annotations, and leaves `MIXED` as it was.
- A pushed `MIXED` starts `build_all.yml` on `MIXED` through `workflow_dispatch`.
- `Orca-Upstream` is also force-pushed: it mirrors upstream `main` exactly,
  even after a history rewrite.

## Consequences

- Nobody can commit on `MIXED` or `Orca-Upstream`; work done there is lost.
- A build runs only when one of the two tips moved, so the cost follows the
  pace of upstream and of `DEV`.
- Removing it: delete `.github/workflows/cosmyx-upstream-sync.yml`,
  `scripts/cosmyx/upstream_sync.py`, its tests and `scripts/cosmyx/just/sync.just`,
  then delete the `MIXED` branch.
