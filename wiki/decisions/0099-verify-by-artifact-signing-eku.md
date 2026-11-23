# 0099. Check our signatures by the Artifact Signing EKUs, with optional pins

## Status

Accepted. Supersedes 0096.

## Context

0096 identified our signatures by `COSMYX_SIGN_SUBJECT`, which is not known
yet: the repository has no variables, and Artifact Signing renews its
short-lived certificates every few days, so no thumbprint can be pinned either.
Every Artifact Signing certificate carries the EKU `1.3.6.1.4.1.311.97.1.0`
next to code signing (`1.3.6.1.5.5.7.3.3`), plus an EKU
`1.3.6.1.4.1.311.97.<...>` that belongs to one identity validation and stays
the same across renewals.

## Decision

- A signature is ours when its certificate carries both EKUs above and, when
  they are set, the subject in the repository variable `COSMYX_SIGN_SUBJECT`
  (as Windows prints it) and the EKU in the repository variable
  `COSMYX_SIGN_EKU`.
- `-Verify` fails on an unsigned file, on a file named directly that is not
  ours, on one of ours without a timestamp, and on any status other than
  `Valid`. It prints the subject and the EKUs of the certificates that signed
  the files named directly, so the pins can be copied from a first run.
- The reuse record only copies a file that is still ours by that rule.
- The verify step finds the installer with
  `scripts/cosmyx/find_windows_installer.ps1`, which matches
  `*_Windows_Installer_*.exe` (the `OrcaSlicer_` upstream name and the
  `CosmoSlice_` product name) and fails when there is none. The workflow
  passes `require-installer: false` only on self-hosted runners, where
  "Start installer Win" does not run.

## Consequences

- Without pins, any Artifact Signing certificate passes, including another
  customer's; setting `COSMYX_SIGN_EKU` (preferred, stable) or
  `COSMYX_SIGN_SUBJECT` closes that.
- Removing the pins: delete the two variables; the EKU check stays.
- A signed build can no longer pass without checking its installer: a
  renamed or missing installer fails the verify step instead of being
  skipped. Relaxing it takes `require-installer: false` in the workflow's
  `# Cosmyx` verify step.
