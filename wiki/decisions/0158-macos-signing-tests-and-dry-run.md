# 0158. macOS signing tests and the ad-hoc dry run

## Status

Accepted.

## Context

Notarisation needs Apple's service and the real certificate, which no local
or test run has. The signing order and the verification still need real
tools to be trusted.

## Decision

- `scripts/cosmyx/tests/test_macos_signing.py` runs the whole flow with a fake
  runner (order, arguments, retries, DMG names, verification rules,
  redaction). On macOS with `cc` and `codesign`, it also compiles an app with
  a nested framework, a dylib and a Python extension, signs it ad-hoc with
  the real codesign in the CI's order, verifies it, and checks that a flipped
  byte fails verification. Elsewhere those tests skip with that reason.
- `scripts/cosmyx/tests/test_macos_signing_wiring.py` reads `build_orca.yml`
  and the action as text and selects its own step by name, ignoring the other
  `# Cosmyx` steps.
- `just mac-sign-dryrun <app>` signs a copy of a local app ad-hoc in the CI's
  order and verifies it; `just mac-sign-status [branch]` shows the signing
  step of the latest "Build all" runs.
- OS exception: signing a macOS app is macOS-only by nature. The dry run and
  the real-tool tests need macOS; the dry run fails with a clear message on
  other systems, the tests skip with a reason. Everything else runs on every
  OS.

## Consequences

- The first signed DEV run is the first end-to-end test of notarisation.
- Removing it: the two test files and `scripts/cosmyx/just/macos-signing.just`.
