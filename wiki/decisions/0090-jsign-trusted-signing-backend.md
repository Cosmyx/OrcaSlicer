# 0090. Sign with Jsign's TRUSTEDSIGNING keystore

## Status

Accepted.

## Context

Cosmyx Windows builds are signed with Azure Artifact Signing (formerly Trusted
Signing), not with upstream's Google Cloud KMS key. Microsoft's
`azure/artifact-signing-action` and the signtool + dlib client run on x64 only,
and the Windows matrix also builds arm64. Upstream already downloads a pinned
Jsign (`JSIGN_VERSION`, `JSIGN_SHA256` in `build_orca.yml`) and calls it from
`scripts/sign_windows.ps1`, which CMake wires into the NSIS installer build.

## Decision

- `scripts/cosmyx/sign_windows_azure.ps1` keeps the interface of
  `scripts/sign_windows.ps1` (`-Path`, `-Verify`, the same file discovery,
  already-signed files left alone, `ORCA_SIGN_REUSE`) and signs with
  `jsign --storetype TRUSTEDSIGNING --keystore <endpoint>
  --alias <account>/<profile> --storepass env:COSMYX_SIGN_TOKEN --alg SHA-256
  --tsaurl http://timestamp.acs.microsoft.com --tsmode RFC3161`.
- It uses upstream's pinned Jsign jar, so a Jsign bump upstream reaches us.
- `COSMYX_SIGN_DRYRUN=1` prints the command and the files instead of signing
  (`just sign-dryrun <path>`).

## Consequences

- Jsign is a Java program: it runs on both runners (Java is set up by the
  `setup` mode of `.github/actions/cosmyx-sign`).
- Removing it: delete the script, its tests and the action, then the hooks
  listed in 0095.
