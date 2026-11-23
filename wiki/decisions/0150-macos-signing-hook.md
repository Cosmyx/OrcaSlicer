# 0150. macOS signing: one action called from one upstream hook

## Status

Accepted.

## Context

Upstream signs and notarises macOS builds in "Sign app and notary", a step
gated on `github.repository == 'OrcaSlicer/OrcaSlicer'` and `main` or
`release/*`. On our repository the build runs "Create DMG without notary"
instead, so DEV and `release/*` DMGs ship ad-hoc signed and Gatekeeper blocks
them. Editing upstream's step would conflict with every upstream change to it;
the region around it changed five times in 2026.

## Decision

- A composite action, `.github/actions/cosmyx-sign-macos`, does the whole
  job; its logic lives in `scripts/cosmyx/macos_signing/` (standard-library
  Python with an injectable runner).
- `build_orca.yml` gets a single `# Cosmyx` step, "Cosmyx sign and notarize
  macOS", between the end of "Create DMG without notary" and the comment of
  "Delete intermediate per-arch artifacts" (14 tagged lines and one blank
  line). Upstream's steps stay as they are and keep skipping on our
  repository.
- The step runs on the combine leg only (`inputs.macos-combine-only`) and
  uses the signing predicate of decision 0098 with `runner.os == 'macOS'`:
  not the upstream repository, not a pull request, not MIXED, DEV or
  `release/*` (or every ref when `COSMYX_SIGN_ALL_REFS` is `true`). It has a
  90-minute timeout (two notarisation rounds).
- The signed DMGs replace the unsigned ones under the same names, so the
  upstream upload steps need no change, and the per-arch bundles are deleted
  only after signing succeeded.

## Consequences

- An upstream change around "Create DMG without notary" can move the hook; the
  wiring test (`test_macos_signing_wiring.py`) pins its neighbours.
- Removing it: delete the step, the action and `scripts/cosmyx/macos_signing/`.
