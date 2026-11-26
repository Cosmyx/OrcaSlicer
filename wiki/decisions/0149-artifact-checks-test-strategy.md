# 0149. Artifact check tests: runtime fixtures and real tools with skips

## Status

Accepted.

## Context

The rules are tested without a build, and the repository commits no binaries.

## Decision

- Every input is created at runtime: PE, Mach-O (thin, fat, a Java class that
  shares the fat magic) and ELF headers, `.mo` catalogues, MSIX zips, fake
  installers through a fake runner.
- Real-tool tests: on macOS with `cc`, a universal binary is compiled and
  checked with the real `lipo` and `codesign` (ad-hoc signed passes, signature
  removed fails); on Linux the running interpreter is checked as an ELF file;
  on Windows, Pester copies the Microsoft-signed `signtool.exe`, flips a byte
  of its code section (exit 1) and clears its certificate table (unsigned).
  Elsewhere they skip with their reason.
- `facts_windows.ps1` is also tested with a fake signtool and a stubbed
  `Get-AuthenticodeSignature`, so it runs under pwsh on any OS.
- The live check of a real run is `just artifact-checks <run id>` once merged,
  or `just artifact-checks-local <run id>` before.

## Consequences

- `just test-scripts` covers the rules on every host; the Windows CI leg runs
  Pester for real (`COSMYX_REQUIRE_PESTER=1`).
