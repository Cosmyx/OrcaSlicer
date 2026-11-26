# 0213. The Flatpak build is off unless a repository variable turns it on

## Status

Accepted.

## Context

`build_all.yml` builds a Flatpak bundle on every push, scheduled and manual
run, and `build_optional.yml` builds it for a pull request labelled
`build-flatpak`. On DEV both call `.github/workflows/build_flatpak.yml`, whose
`flatpak` job then feeds the two Flatpak unit test jobs. On older OrcaSlicer
tags (v2.5.2, for example), which Cosmyx branches are also replayed on, the
`flatpak` job and its two unit test jobs sit directly in `build_all.yml`, and
that job already has its own `if:` condition.

The fork ships no Flatpak, and the leg is often red for reasons outside the
fork's code: for example the upstream wxWidgets pin that broke every Flatpak
build until upstream fixed it. A red leg nobody uses hides the legs that
matter and costs Linux runner time on each build.

The job condition in `build_all.yml` changes often upstream (ten commits on
that line), so editing it would break the zero-conflict rule (decision 0002).
`vars.SELF_HOSTED`, the only existing switch, also moves every other leg to
self-hosted runners.

## Decision

- The `flatpak` job gets the gate wherever the base keeps it, on one line
  tagged `# Cosmyx:`. In `build_flatpak.yml`, where the job has no condition,
  it is one added line, `if: ${{ vars.COSMYX_FLATPAK == 'true' }}`, and no
  upstream line is edited. In `build_all.yml`, where the job has its own
  `if:`, the gate is merged into it as the leading `&&` term:
  `if: ${{ vars.COSMYX_FLATPAK == 'true' && <upstream condition> }}`.
- Without the repository variable the job is skipped, and the two Flatpak unit
  test jobs, which need it to succeed, are skipped with it. This covers both
  callers.
- Setting the repository variable `COSMYX_FLATPAK` to `true` turns the leg back
  on, with no code change.
- `scripts/cosmyx/tests/test_flatpak_off.py` pins the line, its place in the
  `flatpak` job, and that the unit test jobs still depend on that job. It finds
  the job through `scripts/cosmyx/workflow_jobs.py` (`build_flatpak.yml` first,
  then the job block of `build_all.yml`, either line ending), accepts the gate
  as the whole `if:` or as its leading term with no top-level `||` that could
  bypass it, and skips on a base with no flatpak job.

## Consequences

- No Flatpak bundle or Flatpak test results are produced. The Flatpak test
  asset hook of decision 0005 stays, so the leg works again as soon as it is
  turned on.
- Removing this decision means deleting the added `if:` line; the Flatpak leg
  then runs again on every build.
