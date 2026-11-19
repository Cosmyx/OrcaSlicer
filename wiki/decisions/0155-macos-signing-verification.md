# 0155. Verify the signed build before it is uploaded

## Status

Accepted.

## Context

A gap in signing coverage otherwise shows up only when a user opens the app.

## Decision

The last stage fails the step on any problem, listed in the step summary:

- each app: `codesign --verify --deep --strict -vvv`; for every Mach-O file
  and nested bundle (`codesign -d --verbose=4 --entitlements - --xml`): first
  authority `Developer ID Application:`, `TeamIdentifier` equal to `TEAM_ID`,
  the hardened-runtime flag, a secure `Timestamp`, no `get-task-allow`
  entitlement;
- `spctl -a -vvv -t exec` accepts the app with `source=Notarized Developer
  ID`; `stapler validate` passes; `syspolicy_check distribution` passes when
  the tool exists (macOS 14 and later);
- each DMG: `stapler validate`, and `spctl -a -vvv -t open --context
  context:primary-signature` accepts it as a notarised Developer ID.

An ad-hoc dry run (`COSMYX_MAC_SIGN_IDENTITY=-`) checks the deep verify, the
runtime flag, an ad-hoc signature and no `get-task-allow`, and skips
notarisation, stapling and Gatekeeper.

## Consequences

- The verification costs one `codesign` call per Mach-O file (a few minutes).
- The artifact checks report the signature of the uploaded DMG
  (decision 0146).
