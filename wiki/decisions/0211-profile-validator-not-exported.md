# 0211. The profile validator is not exported by Cosmyx builds

## Status

Accepted.

## Context

Upstream uploads `OrcaSlicer_profile_validator_*` artifacts on macOS (a DMG),
Windows and Linux. It is a developer tool for profile authors, not part of
CosmoSlice, and its name would be the only `OrcaSlicer_` artifact left once
the packages are named CosmoSlice (decision 0210). The user does not want it
exported at all.

## Decision

- The package-name stages remove it: `mac-app` deletes the validator app
  from the universal folder (so the Cosmyx signing does not sign it) and its
  DMG; `linux` deletes the validator binary after the last step that runs it,
  so the upstream upload after it finds nothing; `windows` and `mac-upload`
  delete the validator artifact the upstream steps uploaded.
- Kept: the validator is still built, the build's own slice check still
  uses it (the `<sha>-profile-validator-linux-*` artifact, consumed inside the
  same run), and the `check_profiles` workflow is untouched.

## Consequences

- No Cosmyx run lists a profile validator artifact; the artifact checks treat
  it as absent.
- Removing it: drop the `validator*` keys from `packages.json` and their uses
  in `scripts/cosmyx/package_names.py`; the upstream artifacts come back.
