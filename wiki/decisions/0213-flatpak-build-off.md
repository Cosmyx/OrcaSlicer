# 0213. The Flatpak build is off unless a repository variable turns it on

## Status

Accepted.

## Context

`build_all.yml` builds a Flatpak bundle on every push, scheduled and manual
run, and `build_optional.yml` builds it for a pull request labelled
`build-flatpak`. Both call `.github/workflows/build_flatpak.yml`, whose
`flatpak` job then feeds the two Flatpak unit test jobs.

The fork ships no Flatpak, and the leg is often red for reasons outside the
fork's code: for example the upstream wxWidgets pin that broke every Flatpak
build until upstream fixed it. A red leg nobody uses hides the legs that
matter and costs Linux runner time on each build.

The job condition in `build_all.yml` changes often upstream (ten commits on
that line), so editing it would break the zero-conflict rule (decision 0002).
`vars.SELF_HOSTED`, the only existing switch, also moves every other leg to
self-hosted runners.

## Decision

- The `flatpak` job of `build_flatpak.yml` gets one added line,
  `if: ${{ vars.COSMYX_FLATPAK == 'true' }}`, tagged `# Cosmyx:`. No upstream
  line is edited.
- Without the repository variable the job is skipped, and the two Flatpak unit
  test jobs, which need it to succeed, are skipped with it. This covers both
  callers.
- Setting the repository variable `COSMYX_FLATPAK` to `true` turns the leg back
  on, with no code change.
- `scripts/cosmyx/tests/test_flatpak_off.py` pins the line, its place in the
  `flatpak` job, and that the unit test jobs still depend on that job.

## Consequences

- No Flatpak bundle or Flatpak test results are produced. The Flatpak test
  asset hook of decision 0005 stays, so the leg works again as soon as it is
  turned on.
- Removing this decision means deleting the added `if:` line; the Flatpak leg
  then runs again on every build.
