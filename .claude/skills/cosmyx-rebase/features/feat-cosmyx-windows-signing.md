# feat/cosmyx-windows-signing (PR #96)

Analysed commits: `origin/DEV..origin/feat/cosmyx-windows-signing`. Of its 13 commits, the first six (`6cbd27d0fc` to `39c40f609f`) are the shared foundation (T0, PR #86). The feature commits are `137f9674b6`, `a7c8c48ced`, `66ced10a17`, `f47425abb7`, `3f31c7b45f`, `925746e10e`, `a2fbaba0fa`.

## Purpose

Cosmyx Windows builds are Authenticode-signed with Azure Artifact Signing (formerly Trusted Signing): the portable app, the profile validator, the NSIS plugins, the installer payload, the uninstaller and the installer, all timestamped. Upstream signs with Google Cloud KMS only in the upstream repository (`github.repository == 'OrcaSlicer/OrcaSlicer'`), so Cosmyx needs its own backend that keeps the interface of `scripts/sign_windows.ps1`, so upstream's CMake/NSIS hooks reach it unchanged (task T9, decisions 0090 to 0099, `wiki/cosmyx/windows-signing.md`).

Signing runs only on Windows, outside the upstream repository, not for pull requests, not on `MIXED`, on `DEV` or `release/*` (or any non-PR, non-MIXED ref when the repository variable `COSMYX_SIGN_ALL_REFS` is `true`), and only when all six repository secrets exist: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_TRUSTED_SIGNING_ENDPOINT`, `AZURE_CODE_SIGNING_NAME`, `AZURE_CERT_PROFILE_NAME`. With none set the build runs unsigned (a notice); with only some, the setup step fails naming the missing ones (secret values are never printed; the token is masked). OIDC login uses the subject `repo:Cosmyx/OrcaSlicer:ref:refs/heads/<branch>` (decision 0098: no job environment), so each signed branch needs an Entra federated credential. Verify accepts a signature only when the certificate carries the EKUs `1.3.6.1.4.1.311.97.1.0` and code signing `1.3.6.1.5.5.7.3.3`, narrowed by the optional variables `COSMYX_SIGN_EKU` and `COSMYX_SIGN_SUBJECT` (decision 0099).

## Parent and dependencies

- Parent: `DEV`. Depends on the foundation (T0, PR #86), carried in the branch.
- Relies on upstream signing infrastructure that exists on DEV: `CMakeLists.txt` wires `scripts/sign_windows.ps1` into the NSIS build when `ORCA_SIGN_KMS_KEY` is defined at configure time (Cosmyx sets that variable to the sentinel `cosmyx-azure` and never uses the Google backend); `build_orca.yml` job env `JSIGN_VERSION` and `JSIGN_SHA256` (pinned Jsign, read by the action); the `ORCA_SIGN_REUSE` record path `${{ runner.temp }}/signed-files.json` used by upstream's "Start installer Win" step; `$env:BUILD_DIR`, `$env:RUNNER_TEMP/nsis/Plugins`, `build/src/Release/OrcaSlicer_profile_validator.exe`, the installer glob `OrcaSlicer_Windows_Installer_*.exe`.
- Interaction with install-paths (PR #106): `Packaging.cmake` appends to `CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS` after the signing include.
- Azure/GitHub external setup (not in the repository): federated credentials per signed ref, role "Artifact Signing Certificate Profile Signer", the six secrets.
- Tools: Jsign (`--storetype TRUSTEDSIGNING`), Azure CLI `az account get-access-token --resource https://codesigning.azure.net` (override `COSMYX_SIGN_RESOURCE`), `azure/login@v3`, `actions/setup-java@v6`, PowerShell (Pester for tests).

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `scripts/sign_windows.ps1` | upstream hook | One line right after `$ErrorActionPreference = 'Stop'` (before the `# Sectigo issued the certificate...` comment and `$TimestampUrls`): `if ($env:COSMYX_SIGN_BACKEND -eq 'azure') { & (Join-Path (Join-Path $PSScriptRoot 'cosmyx') 'sign_windows_azure.ps1') @PSBoundParameters; return } # Cosmyx`. Hands every call (CI steps and NSIS hooks, `-Path`, `-Verify`) to the Azure script. |
| `.github/workflows/build_orca.yml` | upstream hook (CI) | Three steps, every line tagged `# Cosmyx`: (1) `Cosmyx code signing setup` (id `cosmyx_sign`, `uses: ./.github/actions/cosmyx-sign`, `mode: setup`, passes the six secrets and the two optional variables as inputs) inserted before `- name: Build slicer Win`, i.e. right after the upstream "Set up Java for code signing" step; condition `runner.os == 'Windows' && github.repository != 'OrcaSlicer/OrcaSlicer' && github.event_name != 'pull_request' && github.ref_name != 'MIXED' && (github.ref_name == 'DEV' \|\| startsWith(github.ref_name, 'release/') \|\| vars.COSMYX_SIGN_ALL_REFS == 'true')`. (2) `Cosmyx sign Windows binaries` (`mode: sign`, `if: steps.cosmyx_sign.outputs.enabled == 'true'`) inserted right before `- name: Pack unit tests Win` (after upstream's "Save signed NSIS plugins" step on DEV). (3) `Cosmyx verify Windows signatures` (`mode: verify`, `timeout-minutes: 20`, same enabled condition) inserted after upstream's "Verify Windows signatures" step and before `- name: Upload artifacts Win zip`. |
| `.github/actions/cosmyx-sign/action.yml` | Cosmyx-owned (CI) | Composite action with modes setup, sign, verify and output `enabled`. setup: checks the six inputs, downloads the pinned Jsign and checks its SHA-256, exports `ORCA_SIGN_JSIGN`, `ORCA_SIGN_KMS_KEY=cosmyx-azure`, `COSMYX_SIGN_BACKEND=azure` and the `COSMYX_*` values to `GITHUB_ENV`, sets up Java 21 (Microsoft). sign: `azure/login`, access token exported masked as `COSMYX_SIGN_TOKEN` (and `COSMYX_SIGN_TOKEN_EXPIRES`) so the background installer build inherits it, then `./scripts/sign_windows.ps1 -Path` on the app, the validator and the NSIS plugins, with `ORCA_SIGN_REUSE` set. verify: same checks as upstream's step (7-Zip unpack, silent install, uninstaller) through `-Verify`. Secrets are inputs because a step's `if:` cannot read the `secrets` context. |
| `scripts/cosmyx/sign_windows_azure.ps1` | Cosmyx-owned (script) | Same parameters as `sign_windows.ps1`; finds `.exe`, `.dll`, `.pyd` recursively (files named directly are signed whatever the extension), skips signed ones, supports the `ORCA_SIGN_REUSE` record (copy only if the file is still ours), `COSMYX_SIGN_DRYRUN`, `-Verify`, never prints the token, fails clearly on an expired token. |
| `scripts/cosmyx/just/signing.just` | Cosmyx-owned (recipes) | `sign-dryrun PATH` (pwsh, dry run). |
| `scripts/cosmyx/tests/sign_windows_azure.Tests.ps1` | test | Pester suite (see Verification). |
| `scripts/cosmyx/tests/test_windows_signing_wiring.py` | test | unittest on the workflow and the action. |
| `wiki/cosmyx/windows-signing.md`, `wiki/decisions/0090` to `0099` | docs | Backend, OIDC, token resource and lifetime, signed refs, hooks (0095), verify, test strategy, secrets (0098), EKU (0099). 0091 and 0093 are superseded by 0098; 0096 by 0099. |
| `CHANGELOG.md` | docs | Line under `<!-- cosmyx-slot: T9 -->` (CI-release area). |
| `.github/workflows/cosmyx-checks.yml` | CI | Foundation file; its path filters include `scripts/sign_windows.ps1`, `.github/actions/**`, `.github/workflows/cosmyx-*.yml`. |

Foundation hooks (shared, identical in every branch): the five lines of decision 0002 (libslic3r CMake `include(Cosmyx/Cosmyx.cmake) # Cosmyx` after `source_group(TREE ...)`; GUI CMake `include(GUI/Cosmyx/Cosmyx.cmake) # Cosmyx`; `add_subdirectory(cosmyx) # Cosmyx` between `slic3rutils` and `fff_print`; two lines in `PrintConfig.cpp`; one include in `GCode.cpp`).

## Rebase risk zones

This is the riskiest branch for a release-tag rebase: the signing workflow of v2.5.1 predates the DEV rework.

| Upstream file | v2.5.1 vs DEV | Churn 2026 |
|---------------|---------------|-----------|
| `scripts/sign_windows.ps1` | Differs by 1 insertion, 40 deletions: the tag lacks the `ORCA_SIGN_REUSE` feature (added on DEV by `cbf282e6b3`, 2026-11-16, "Sign Each Windows Binary Once and Keep the Signed NSIS Plugins" (#17483), three days after the 2.5.1 tag). The hook anchor `$ErrorActionPreference = 'Stop'` after the `param(...)` block exists on both. Because Cosmyx dispatches before upstream's logic, the Azure script carries its own reuse implementation and does not depend on upstream's. | 2 (`73e64d3bc5`, `cbf282e6b3`) |
| `.github/workflows/build_orca.yml` | Anchors present on the tag: "Set up Java for code signing" (line 503), `Build slicer Win` (510), "Authenticate to Google Cloud for code signing", "Sign Windows binaries" (544), "Pack unit tests Win" (556), "Verify Windows signatures" (590), "Upload artifacts Win zip". Absent on the tag: "Restore signed NSIS plugins", "Save signed NSIS plugins", "Start installer Win" (the tag builds the installer in a foreground "Create installer Win" step running `cpack -G NSIS`), and `ORCA_SIGN_REUSE`. Consequences on the tag: the sign step is placed before "Pack unit tests Win" as before (a "Build system preset cache (Windows)" step sits between "Build slicer Win" and the Google auth on the tag); `COSMYX_SIGN_TOKEN` in `GITHUB_ENV` still reaches the foreground cpack; the cpack step's own `ORCA_SIGN_REUSE` is unset, so the installer payload is signed again (slower, but valid; the action's `ORCA_SIGN_REUSE` only applies inside the sign step). The action's comment about "Start installer Win" does not describe the tag. Job env `JSIGN_VERSION: '7.6'` and `JSIGN_SHA256` are present on both. | 86 |
| `CMakeLists.txt` | `if (WIN32 AND DEFINED ENV{ORCA_SIGN_KMS_KEY})` block writing `sign_windows.nsh` and setting `CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS` is present on the tag (lines ~1386 to 1408). No Cosmyx edit here. | 73 |
| Foundation anchors (`src/libslic3r/CMakeLists.txt`, `src/slic3r/CMakeLists.txt`, `tests/CMakeLists.txt`, `PrintConfig.cpp`, `GCode.cpp`) | All present on the tag. | 127, 205, 9, 385, 342 |

Everything else the branch needs is on DEV and the tag: `BUILD_DIR`, the validator path, the installer glob, Jsign pin. If the base is changed to a tag older than the DEV signing work, re-check the step names with `git show upstream/<tag>:.github/workflows/build_orca.yml | grep -n "name:.*[Ss]ign"`.

## Intent to preserve

- Cosmyx Windows builds on DEV and `release/*` are signed with Azure Artifact Signing when the six secrets exist, unsigned otherwise, never signed for pull requests, forks without secrets, MIXED or the upstream repository.
- Upstream's Google Cloud steps stay in place and skipped on our repository (their condition requires the upstream repository). Upstream's CMake wiring is unchanged and is reached through the `ORCA_SIGN_KMS_KEY` sentinel and the one-line dispatch.
- The token is masked and never printed; secrets never appear in an `if:`; no job-level `environment:`; no repository variables are required to sign.
- Verification of our signatures is by EKU (plus optional pins), timestamp required, status `Valid`.

If upstream rewrote the hooked code: if upstream changes the signing script's interface or parameter names, keep the dispatch line as the first statement after the param block, and update `sign_windows_azure.ps1` to the new parameters (the dispatch uses `@PSBoundParameters`). If upstream restructures the signing steps (merged, renamed, moved to a composite action or reusable workflow), re-place our three steps by their meaning: setup before the build, sign after the build and before anything that packs or builds the installer, verify after upstream's verification; the wiring test selects steps by name, update the names it expects. If upstream drops `ORCA_SIGN_KMS_KEY`, replace the sentinel with whatever new gate wires signing into CPack. If upstream moves the NSIS signing include, keep ours appended and never replacing. If the Jsign pin moves to another variable, update the action's check for `JSIGN_VERSION`/`JSIGN_SHA256`.

## Verification

Pester (`scripts/cosmyx/tests/sign_windows_azure.Tests.ps1`, Describe "Cosmyx Azure signing"): dry run prints the Jsign TRUSTEDSIGNING command; finds `.exe`, `.dll`, `.pyd`; signs a file named directly; leaves signed files; does nothing when all are signed; reuse record copy and its refusals (other subject, no Artifact Signing EKU); never prints the token; fails on missing path and missing variables; needs `COSMYX_SIGN_TOKEN`; expired token error; `-Verify` (pass, unsigned, other subject, missing timestamp, damaged signature, pinned subject, without pins any Artifact Signing certificate and prints signer, missing EKUs, no EKU, timestamp and Valid still required, EKU pin accept and reject); dispatch from `sign_windows.ps1` (hands over when `COSMYX_SIGN_BACKEND` is `azure`, passes `-Verify`, keeps upstream otherwise).

unittest (`test_windows_signing_wiring.py`): signing steps present once and in order (selected by name), only the setup step carries the id `cosmyx_sign`, setup passes the six secrets, no secret in a condition, setup condition keeps the signed refs, sign and verify follow the `enabled` output, no job `environment:`, no repository variables for the settings; action tests: `enabled` output comes from the settings step, the settings step checks every secret, setup work waits for it, pins reach the script. Run `just test-scripts` (set `COSMYX_REQUIRE_PESTER=1` on Windows; Pester runs only when `pwsh` exists). `just sign-dryrun <path>` for a local dry run. `just decisions` for the register.

Real proof only in CI: start `build_all` on DEV (`just build-all DEV`) with the secrets present; the "Cosmyx verify Windows signatures" step prints `Signer of the files named directly: Subject ..., EKU ...`; copy the EKU into `COSMYX_SIGN_EKU` to pin it. A signed ref without its federated credential fails at "Log in to Azure" with `AADSTS70021`.

## Known pitfalls

- `a2fbaba0fa`: the wiring test assumed the three signing steps were the only `# Cosmyx` steps of `build_orca.yml`; other branches add their own (version naming step, source preparation, macOS signing), so the test broke on combined trees. It now selects the steps by name and checks order and uniqueness.
- `f47425abb7`: the repository holds the Azure settings as secrets, not variables, and `if:` cannot read secrets; the first version read `vars.*` that were never set. The action now takes secrets as inputs and returns `enabled`.
- The first OIDC design used a job environment (`environment:azure-signing`); abandoned (decision 0098) because it would touch an upstream job header and affect Linux/macOS legs; the credential for `environment:azure-signing` no longer matches and per-ref credentials are required (Entra has no wildcards in plain federated credentials; max 20).
- Upstream's "Start installer Win" forces `ORCA_SIGN_TOKEN` to upstream's empty token in its own env, so the token reaches the background cpack as `COSMYX_SIGN_TOKEN` in `GITHUB_ENV` (masked). Do not use `ORCA_SIGN_TOKEN`.
- NSIS plugins are re-signed on every signed run (upstream caches them per certificate; Azure certificates change every few days).
- Without pins, any Artifact Signing certificate passes verify, including another customer's; set `COSMYX_SIGN_EKU`.
- CRLF/Windows: Pester and PowerShell files must stay LF in the repository (shared line-ending rule).
- v2.5.1 pass (copy tip `a55da7f26c`): `137f9674b6` conflicted in `build_orca.yml` twice: the sign step's DEV context ("Save signed NSIS plugins") does not exist on the tag, so the step goes right before "Pack unit tests Win" with no upstream line taken from DEV; the verify step's context differs because the tag has "Pack app" and "Pack PDB" between "Verify Windows signatures" and "Upload artifacts Win zip". Verify was placed right after upstream's verify step (before "Pack app"). The later commits replayed clean and the wiring test passes.
- v2.5.2 pass (copy tip `a88a79d944`): the two `build_orca.yml` conflicts replayed by `rerere` from the v2.5.1 resolution (v2.5.2 does not touch `build_orca.yml`); no manual edit.

## Shared files with other branches

- `.github/workflows/build_orca.yml`: also edited by `feat/cosmyx-version` (one step after the version steps) and by the macOS signing and source preparation branches; keep each step block separate and tagged `# Cosmyx`.
- `scripts/sign_windows.ps1` (only this branch edits it), `CMakeLists.txt` top level (not edited here, but `feat/cosmyx-install-paths` hooks the same CPack block; its legacy-removal include is appended after upstream's signing include).
- `.github/workflows/cosmyx-checks.yml`, `justfile` (imports `scripts/cosmyx/just/signing.just`, created here), `scripts/cosmyx/{decisions.py,run_script_tests.py,tests/test_foundation.py}`, `CHANGELOG.md` (slot T9), `wiki/decisions` (0090 to 0099).
- `.github/actions/` is a Cosmyx-owned folder that other branches (macOS signing, branding) may also add actions to.
