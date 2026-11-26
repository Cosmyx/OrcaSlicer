# 0144. Check modes mirror the signing predicate; strict mode

## Status

Accepted.

## Context

Only some builds are signed (0098). Checking an unsigned pull request as if it
were a release would always fail; ignoring a release that should have been
signed would hide a broken pipeline.

## Decision

- `enforce`: the 0098 predicate holds (not upstream, not a pull request, not
  MIXED, DEV or `release/*` or `COSMYX_SIGN_ALL_REFS`, and the six Azure
  secrets are set). Every Windows signature rule is a failure when broken.
- `not-configured`: a ref that would be signed but the secrets are not all set.
  Signatures are reported with the notice "Windows signing not configured
  (0098): reported, not enforced"; a failure in strict mode. Partly set
  secrets also print a warning naming the missing ones.
- `report`: pull requests, MIXED and other refs; signatures are reported only,
  with the count of unsigned files.
- The secrets are read in the check run, not in the build run: both are the
  same repository secrets, so a change between the build and the check would
  show as a wrong mode.
- Arch, payload, ELF, smoke, slice, names, translations and models are
  enforced in every mode.
- Required artifacts (Windows x64 portable and installer, the universal DMG
  except on schedule runs, which do not build it, the Linux x64 AppImage) must
  be present on successful DEV and `release/*` builds of push, dispatch and
  schedule runs; elsewhere the check is skipped by design.
- Strict mode (dispatch only) turns every skip into a failure, except skips by
  design (a binary that cannot run on the runner, a fork build, no required
  set for that run). Without that exception an arm64 build could never pass.

## Consequences

- Release candidates should be checked with `just artifact-checks <id> true`.
- Removing the modes means one fixed policy for every build.
