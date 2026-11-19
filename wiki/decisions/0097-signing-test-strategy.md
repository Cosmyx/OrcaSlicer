# 0097. Testing the signing script without signing

## Status

Accepted.

## Context

Signing needs Windows, Java, Jsign and a live Azure account. The script tests
must run under `pwsh` on any OS, in `just test-scripts`.

## Decision

- `scripts/cosmyx/tests/sign_windows_azure.Tests.ps1` (Pester 5) runs the
  script as a dry run and replaces `Get-AuthenticodeSignature` with a global
  stub function (a function takes precedence over a cmdlet of the same name).
- It covers the Jsign command, file discovery, skipping signed files, the reuse
  record, missing variables, the expired-token error, every `-Verify` failure,
  and the dispatch hook in `scripts/sign_windows.ps1`.
- The real signing is validated by a `build_all` run on DEV once the Azure
  settings exist.

## Consequences

- A change to the Jsign arguments must update the dry-run assertions.
