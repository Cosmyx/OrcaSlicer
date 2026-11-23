# 0156. Artifact checks enforce Developer ID on signed macOS builds

## Status

Accepted. Amends 0146.

## Context

Decision 0146 reported the macOS bundle signature only, because the build had
no Developer ID certificate. T15 signs and notarises the universal app and the
profile validator when the seven Apple secrets are set (decisions 0150,
0151). The per-arch DMGs (`OrcaSlicer_Mac_arm64_*`, `OrcaSlicer_Mac_x86_64_*`)
stay ad-hoc signed.

## Decision

- The resolve job computes a second mode, `mac_mode`: the 0098 predicate
  (not upstream, not a pull request, not MIXED, DEV or `release/*` or
  `COSMYX_SIGN_ALL_REFS`) and the seven Apple secrets set, read as
  `COSMYX_HAS_<SECRET>` presence flags. Predicate true but secrets missing:
  `not-configured` (a notice; a failure in strict mode). Otherwise `report`.
  The macOS leg runs with `mac_mode`, the other legs with the Windows mode.
- The macOS leg receives the `TEAM_ID` secret as `COSMYX_MAC_TEAM_ID` (masked
  by GitHub); it is the only secret value the checks read.
- In `enforce` mode, for the families marked `developer_id` in
  `data/expectations.json` (the universal app and the profile validator):
  - `bundle_sig`: Developer ID, deep verify, the team; a failure otherwise;
  - `macho_identity`: every Mach-O file has a Developer ID authority, the team,
    the hardened runtime, a secure timestamp and no `get-task-allow`;
  - `dmg_sig`: the DMG is Developer ID signed by the team;
  - `notarization`: the DMG and each app in it pass `stapler validate`;
    Gatekeeper accepts the apps (`spctl -t exec`) and the DMG (`spctl -t open
    --context context:primary-signature`) as notarised Developer ID.
  An empty `COSMYX_MAC_TEAM_ID` in `enforce` mode is a failure.
- In `report` and `not-configured` modes, and for the per-arch families, the
  0146 rules stay as they were (`bundle_sig` reported as a warning).

## Consequences

- A signed DEV build that loses its notarisation or a nested signature fails
  `cosmyx/artifact-checks`, not only the build step.
- The rules share `parse_display` and `file_problems` with the signing script
  (`scripts/cosmyx/macos_signing/verify.py`), so both read codesign the same
  way.
- Removing it: drop `mac_mode` from `signing_policy.py`, `cli.py` and the
  workflow, the enforce branches of `macos.py`, the `developer_id` flags, and
  set 0146 back to Accepted.
