# 0227. Trim the large MIXED caches after each Build all run

## Status

Accepted.

## Context

The upstream sync rebuilds MIXED (DEV merged with upstream) and starts
"Build all" on it. That upstream workflow saves about 9 GB of caches on
`refs/heads/MIXED`: compiler caches (`ccache-*`, new keys on every run, since
the key holds the run id) and `flatpak-builder-*`. The repository cache limit
is 10 GB and GitHub evicts the least recently used entries, so the deps caches
of other branches and pull requests (for example the macOS one, about 135 MB,
saved by "Build Deps") were evicted before "Build OrcaSlicer" restored them
with `fail-on-cache-miss`, and those builds failed.

A cache saved on `refs/heads/MIXED` is only readable by MIXED runs. The
zero-conflict rule forbids changing how upstream's workflows save caches.

## Decision

- A Cosmyx workflow, `.github/workflows/cosmyx-cache-trim.yml`, runs on
  `workflow_run` of "Build all", filtered to the `MIXED` branch, and only on
  the fork (`github.repository != 'OrcaSlicer/OrcaSlicer'`) for a MIXED of this
  repository (head repository check). It has `actions: write` only and uses
  no action beyond `actions/checkout`.
- On `requested` it watches the run and trims every five minutes until the
  run completes (at most 330 minutes); on `completed` it trims once more.
  Watching keeps the peak low, since jobs save their caches one by one over a
  run of a few hours.
- `scripts/cosmyx/ci/cache_trim.py` selects, on `refs/heads/MIXED` only (a
  constant, not a setting), every key starting with `ccache-` or
  `flatpak-builder-` and every other entry of 256 MB or more
  (`COSMYX_CACHE_TRIM_THRESHOLD_MB` repository variable). Deps caches (key
  containing `orcaslicer_deps`) are never deleted, whatever their size:
  "Build OrcaSlicer" restores them with `fail-on-cache-miss`, so deleting one
  mid-run would fail MIXED. The cmake, msys2 and nsis caches (1-130 MB) stay
  under the threshold, and MIXED still skips its deps build.
- Rejected: editing `build_all.yml` or the build workflows to skip saving on
  MIXED (an upstream file, conflicts on every sync); a trim step in the
  upstream sync (it runs before the build saves anything); a scheduled sweep
  (caches would sit at the limit between sweeps).

## Consequences

- MIXED compiles cold every time (no ccache, no flatpak-builder cache): its
  builds are slower, which is acceptable for a canary build.
- A cache deleted while a later job of the same run restores it is a cache
  miss for that job, never a failure: ccache and flatpak-builder caches are
  restored without `fail-on-cache-miss`.
- The watcher holds one ubuntu runner for the length of each MIXED build.
- `workflow_run` fires only from the copy of the workflow on the default
  branch, so the trim works once this is merged into DEV.
- Removing this: delete the workflow, `scripts/cosmyx/ci/cache_trim.py` and
  its test. MIXED caches then fill the repository cache again.
