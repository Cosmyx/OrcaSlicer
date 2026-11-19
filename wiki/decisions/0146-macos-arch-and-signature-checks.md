# 0146. macOS: architectures and arm64 signatures enforced, Developer ID reported

## Status

Amended by 0156 (Developer ID rules on signed builds).

## Context

Apple silicon refuses to run arm64 code without a signature (an ad-hoc one is
enough). The Cosmyx build has no Developer ID certificate yet, so bundles are
ad-hoc signed and not notarised.

## Decision

- Every DMG (except the `Mac_bundle` tarballs) is attached read-only with
  `hdiutil attach -readonly -nobrowse`, and every Mach-O file inside it is
  checked:
  - `lipo -archs` gives exactly the family's architectures (universal: arm64
    and x86_64; per-arch builds: their own), unless an `arch-exempt` entry
    covers the file;
  - `codesign --verify --strict --arch arm64` passes for every file with an
    arm64 slice (object files and x86_64-only files are skipped by design).
- Each `.app` is checked with `codesign --verify --deep --strict` and its
  signature class is read with `codesign -dv`; anything but Developer ID is a
  warning "not Developer-ID signed (expected, 0146)".

## Consequences

- Developer ID, notarisation, `stapler`, `spctl` and a `COSMYX_MAC_TEAM_ID`
  pin are deferred until a certificate exists; then the bundle check becomes
  enforced.
- Removing it: drop `macos.py` and its tests.
