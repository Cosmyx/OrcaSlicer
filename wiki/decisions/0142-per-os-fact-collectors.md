# 0142. OS exception: per-OS fact collectors, policy in Python

## Status

Accepted.

## Context

The rules are OS neutral, but the facts are not: Authenticode is read with
`signtool` and `Get-AuthenticodeSignature` (Windows), Mach-O signatures and
slices with `codesign` and `lipo`, disk images with `hdiutil` (macOS), and
AppImages need Linux.

## Decision

- Each OS job collects facts with that OS's own tools behind one interface per
  OS: `facts_windows.ps1` (the only PowerShell, it decides nothing and writes
  JSON lines), and `macos.py` / `linux.py` calling the native tools through an
  injectable runner.
- Every rule lives in Python (`policy_windows.py`, `macos.py`, `linux.py`,
  `content.py`), tested on any OS from fact records or a fake runner.
- Real-tool tests run on the OS that has the tools and skip elsewhere with
  their reason (decision 0149).

## Consequences

- A rule change never touches the collectors; a new fact needs a collector
  change and its test.
- Removing the exception means dropping the OS-specific checks.
