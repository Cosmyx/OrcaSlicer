# 0143. Windows signature and payload rules

## Status

Accepted.

## Context

T9 signs the Windows build with Azure Artifact Signing (decisions 0098 and
0099). The installer is built from the portable folder after it is signed and
reuses the signed files.

## Decision

- Every PE file found by its magic bytes is checked: in the portable folders,
  the NSIS installer, its payload (unpacked with 7-Zip 23.01 or newer, else the
  check fails), the uninstaller a silent install writes (x64 only; arm64 is
  skipped by design), the profile validator and the files inside the MSIX
  package. The MSIX package itself is unsigned by design (the Store signs it).
- Facts: `signtool verify /pa /all /tw /v` (newest Windows Kits signtool, one
  retry on a revocation or network failure) and `Get-AuthenticodeSignature`
  (primary signature).
- Enforced (decision 0144): signtool exit 0 (1 or 2 fail), status `Valid`, and
  each file either ours with a timestamp, or matched by a vendor allowlist
  entry (publisher subject, timestamp unless the entry says otherwise), or an
  unsigned file matched by an `unsigned-ok` entry that is not one of the files
  the build signs by name.
- Ours follows 0099: the certificate carries the Artifact Signing EKU
  `1.3.6.1.4.1.311.97.1.0` and code signing `1.3.6.1.5.5.7.3.3`, plus the
  optional pins `COSMYX_SIGN_EKU` (format `1.3.6.1.4.1.311.97.<n>...`) and
  `COSMYX_SIGN_SUBJECT`. Without pins the check passes with a warning that
  prints the subjects and EKUs seen, so the pins can be copied; with the
  subject only, a warning suggests the EKU. No thumbprint is pinned.
- In every mode, the payload holds every PE of the portable folder of the same
  architecture with the same SHA-256 (NSIS `$INSTDIR` prefixes stripped).

## Consequences

- Without pins, any Artifact Signing certificate passes; set
  `COSMYX_SIGN_EKU` to close that.
- Removing it: drop `policy_windows.py`, `facts_windows.ps1` and their tests.
