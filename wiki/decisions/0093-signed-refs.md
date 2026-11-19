# 0093. Which builds are signed

## Status

Accepted.

## Context

Signing calls a paid service and needs an Azure login whose federated
credentials name each ref (0091). MIXED (DEV merged with upstream, rebuilt by a
schedule) and pull requests run code that was not reviewed for release.
`build_all.yml` only triggers on pushes to `main` and `release/*`, so DEV is
built by hand (`just build-all DEV`).

## Decision

- The Cosmyx steps run only when every one of these holds: Windows runner, not
  the upstream repository, not a pull request, not MIXED,
  `vars.COSMYX_SIGN_ACCOUNT` is set, and the ref is DEV or `release/*` (or
  `vars.COSMYX_SIGN_ALL_REFS` is `true`, for a one-off test on a feature
  branch, which also needs its own federated credential).
- Upstream's own signing steps stay skipped on our repository: their condition
  requires `github.repository == 'OrcaSlicer/OrcaSlicer'`.

## Consequences

- Without the repository variables the build is unchanged and unsigned.
- Removing it: delete the three `# Cosmyx` steps in `build_orca.yml`.
