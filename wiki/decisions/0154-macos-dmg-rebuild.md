# 0154. Rebuild the DMGs from the signed apps under the same names

## Status

Accepted.

## Context

"Create DMG without notary" already wrote `OrcaSlicer_Mac_universal_<ver>.dmg`
and, when the profile validator exists,
`OrcaSlicer_profile_validator_Mac_universal_<ver>.dmg`, from unsigned apps. The
upload steps read those names.

## Decision

- For each app, `build/universal/<app>_dmg` is emptied in place, the stapled
  app is copied with `ditto`, `Applications` links to `/Applications`, and
  upstream's `create_dmg` (from `scripts/create_dmg.sh`, with `retry` from
  `scripts/retry.sh`) writes `<app>_Mac_universal_<ver>.dmg` in the workspace,
  overwriting the unsigned one.
- The volume name is the app's `CFBundleName`, or its file name without
  `.app` when there is none.
- Each DMG is signed (`codesign --force --timestamp`, no runtime or
  entitlements: those apply to code), notarised and stapled.

## Consequences

- The profile validator's volume name follows its bundle name rather than
  upstream's literal "OrcaSlicer Profile Validator".
- Removing it: `dmg.py`.
