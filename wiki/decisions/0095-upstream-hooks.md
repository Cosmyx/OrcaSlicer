# 0095. How Cosmyx signing plugs into the upstream build

## Status

Accepted.

## Context

Upstream wires signing into the NSIS installer from `CMakeLists.txt`: when
`ORCA_SIGN_KMS_KEY` is defined at configure time, it writes
`build/sign_windows.nsh` with `!system` (the payload), `!uninstfinalize` and
`!finalize` calling `scripts/sign_windows.ps1 -Path`. "Start installer Win"
runs cpack in a background `pwsh` started from its step, with
`ORCA_SIGN_TOKEN` and `ORCA_SIGN_REUSE` in the step's own `env`, which
overrides any value from `GITHUB_ENV`.

## Decision

- `scripts/sign_windows.ps1` gets one line after
  `$ErrorActionPreference = 'Stop'`: when `COSMYX_SIGN_BACKEND` is `azure`, it
  runs `scripts/cosmyx/sign_windows_azure.ps1` with the same parameters and
  returns. Every caller (CI steps, the NSIS hooks) reaches our backend.
- The `setup` mode exports `ORCA_SIGN_KMS_KEY=cosmyx-azure`, a sentinel that
  only opens the CMake gate; `CMakeLists.txt` is not edited.
- The token reaches the background cpack as `COSMYX_SIGN_TOKEN` in
  `GITHUB_ENV` (masked first): the background process inherits the step's
  environment, and `ORCA_SIGN_TOKEN` cannot be used because that step forces it
  to upstream's empty token.
- The `sign` mode uses the same reuse record path as "Start installer Win"
  (`${runner.temp}/signed-files.json`), so cpack copies the signed files
  instead of signing them again.
- `build_orca.yml` gets three steps, every line tagged `# Cosmyx`: setup before
  "Build slicer Win", sign before "Pack unit tests Win", verify after upstream's
  "Verify Windows signatures".

## Consequences

- The NSIS plugins are signed on every signed run (upstream caches them per
  certificate; Artifact Signing certificates change every few days).
- The token is visible to every later step of the job, as upstream's would be
  to the steps it is given to.
- Removing it: delete the dispatch line and the three steps; nothing else in
  upstream files changes.
