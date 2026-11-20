# ci/cosmyx-macos-signing (PR #105)

## Purpose

DEV and `release/*` macOS builds were ad-hoc signed and not notarised, so Gatekeeper blocked them. This feature signs the universal app with the Cosmyx Developer ID Application certificate (inside out, hardened runtime, secure timestamp, `scripts/disable_validation.entitlements`, never `--deep`), notarises and staples each `.app`, rebuilds `OrcaSlicer_Mac_universal_<ver>.dmg` and `OrcaSlicer_profile_validator_Mac_universal_<ver>.dmg` under the same names from the stapled apps, signs, notarises and staples the DMGs, and verifies everything before upload. It also makes the artifact checks enforce Developer ID, team, hardened runtime, no `get-task-allow`, notarisation and stapling on those DMGs (decision 0156). It uses the seven Apple secrets upstream already names (`BUILD_CERTIFICATE_BASE64`, `P12_PASSWORD`, `KEYCHAIN_PASSWORD`, `MACOS_CERTIFICATE_ID`, `APPLE_DEV_ACCOUNT`, `APP_PWD`, `TEAM_ID`); none set means off with a notice, some set fails and names the missing ones. The notary password never appears on a command line (decision 0159).

## Parent and dependencies

Parent: `ci/cosmyx-artifact-checks` (#100) (so it also depends on the foundation #86); own commits `8fc79e1bea`, `79c70389b2`, `8d76c7de4d`, `a0de239402`, `e6524bdeba`; decisions 0150-0159. Upstream things it relies on: the `build_orca.yml` macOS combine leg (`inputs.macos-combine-only`), the step name "Create DMG without notary", the helper `scripts/create_dmg.sh` (`create_dmg`, `retry`), `scripts/disable_validation.entitlements`, the directories `build/universal/OrcaSlicer/OrcaSlicer.app` and `OrcaSlicer_profile_validator.app`, the env var `env.ver`, runner tools `codesign`, `notarytool`, `stapler`, `spctl`, `syspolicy_check`, `hdiutil`, `security`, `pf`.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `.github/workflows/build_orca.yml` | upstream hook | One 15-line step inserted between the "Create DMG without notary" step (the one that builds the unsigned DMGs) and the comment "# Delete the per-arch bundles only after signing/DMG creation succeeded..." / step "Delete intermediate per-arch artifacts". Exact lines, all tagged `# Cosmyx`: `- name: Cosmyx sign and notarize macOS # Cosmyx`; `if: runner.os == 'macOS' && inputs.macos-combine-only && github.repository != 'OrcaSlicer/OrcaSlicer' && github.event_name != 'pull_request' && github.ref_name != 'MIXED' && (github.ref_name == 'DEV' \|\| startsWith(github.ref_name, 'release/') \|\| vars.COSMYX_SIGN_ALL_REFS == 'true') # Cosmyx`; `timeout-minutes: 90 # Cosmyx`; `uses: ./.github/actions/cosmyx-sign-macos # Cosmyx`; `with: # Cosmyx` and nine input lines `version`, `self-hosted`, `certificate-base64`, `p12-password`, `keychain-password`, `certificate-id`, `apple-id`, `app-password`, `team-id`, each ending `# Cosmyx`, followed by one blank line. |
| `.github/actions/cosmyx-sign-macos/action.yml` | CI (Cosmyx-owned) | Composite action: secrets check, temporary keychain, Developer ID identity check, pf rule blocking UDP 443 on hosted runners (stapler over TCP), runs `scripts/cosmyx/macos_signing/cli.py run`, uploads `cosmyx-notary-log-<ver>` on failure, always cleans keychain and pf. |
| `scripts/cosmyx/macos_signing/{__init__,cli,discover,dmg,notarize,sign,verify}.py` | Cosmyx-owned | Inside-out signing, notarisation via keychain profile (password on stdin), DMG rebuild, verification, `dryrun` and `status` subcommands. |
| `scripts/cosmyx/just/macos-signing.just` | Cosmyx-owned | Recipes `mac-sign-dryrun`, `mac-sign-status`. |
| `.github/workflows/cosmyx-artifact-checks.yml`, `scripts/cosmyx/artifact_checks/{cli,macos,records,report,signing_policy}.py`, `data/expectations.json` | CI / Cosmyx-owned | New `mac_mode` output (same predicate plus the seven secret flags), `COSMYX_MAC_TEAM_ID`, `--mac-mode`, `developer_id: true` on the universal DMG and validator DMG families; per-Mach-O identity, DMG signature and notarisation rules in enforce mode. |
| `scripts/cosmyx/tests/test_macos_signing.py`, `test_macos_signing_wiring.py`, `test_breaker_info_plist.py`, `test_breaker_notary_password_argv.py`, additions to `test_artifact_checks_{macos,report,signing_policy}.py`, `test_foundation.py` | test | Fake runner everywhere, real ad-hoc signing on macOS; wiring tests parse `build_orca.yml`. |
| `wiki/cosmyx/macos-signing.md`, `wiki/cosmyx/artifact-checks.md`, `wiki/decisions/0150-0159`, `0003`, `0146` | docs | Design; 0003 and 0146 amended. |
| `CHANGELOG.md` | docs | T15 slot line. |

## Rebase risk zones

| Upstream file | v2.5.1 vs DEV | Churn |
|---|---|---|
| `.github/workflows/build_orca.yml` (macOS combine leg) | The anchors exist in both: step "Create DMG without notary" (`if: github.ref != 'refs/heads/main' && runner.os == 'macOS' && inputs.macos-combine-only` in the tag) is followed by the comment and step "Delete intermediate per-arch artifacts" (tag line ~383). Differences elsewhere: the tag lacks DEV's per-arch "Create DMG ${{ inputs.arch }} without notary" step and the `github.event_name == 'pull_request'` gating, and the tag's Windows `if:` lacks the clang compiler conditions. Upstream's own "Sign app and notary" step (guarded `github.repository == 'OrcaSlicer/OrcaSlicer'`, which keeps it off on the fork) is present in both. | 20 commits since 2026-01 |
| `scripts/create_dmg.sh`, `scripts/disable_validation.entitlements`, `scripts/retry.sh` | Not diffed by this branch but required: must still exist with the same function names. | check |

## Intent to preserve

- DMG file names do not change; the shipped macOS app and DMGs are Developer ID signed, notarised and stapled on DEV and `release/*`; PR, MIXED and other refs keep the ad-hoc DMG.
- Signing never uses `--deep`, never echoes a secret, never leaves the temporary keychain or pf rule behind, and fails (not silently skips) when only some secrets are set.
- The hook is exactly one step, with every line tagged `# Cosmyx`, placed after the unsigned DMGs exist and before the upload steps, so it signs what is uploaded. If upstream reshapes the macOS combine job (new step names or DMG creation moved), re-place the same step after whichever step produces `build/universal/OrcaSlicer/*.app` and the unsigned DMGs and before "Upload artifacts mac"; update `WorkflowHookTests.test_step_sits_after_the_unsigned_dmg_and_before_the_uploads` accordingly. Never edit upstream's own signing step.

## Verification

- `just test-scripts`: `test_macos_signing.py` (27 tests), `test_macos_signing_wiring.py` (`WorkflowHookTests`: step present once, position, blank line, gate, seven secrets, every line tagged, upstream signing stays upstream-only; `ActionTests`), `test_breaker_notary_password_argv.py`, `test_breaker_info_plist.py`, `test_artifact_checks_macos.py`, `test_artifact_checks_signing_policy.py`, `test_artifact_checks_report.py`.
- `just mac-sign-dryrun <path to .app>` on a Mac (ad-hoc signing in CI order).
- CI: dispatch Build all on the branch with the secrets present on a DEV-like ref (or `COSMYX_SIGN_ALL_REFS=true`); the step summary must list all verifications; `just mac-sign-status`; the artifact checks macOS leg runs in `enforce` mode. Manually: `spctl -a -t open --context context:primary-signature -v <dmg>` and `xcrun stapler validate`.

## Known pitfalls

- e6524bdeba: `notarytool ... --password <APP_PWD>` exposed the password in the process list for up to 40 minutes; credentials are now stored as a keychain profile (password on stdin, no terminal). Notarisation refuses to run without the temporary keychain. Also `dmg.volume_name` mis-handled non-dict plist roots.
- Stapler fetches over HTTP/3 (UDP 443) on hosted runners and times out: the pf rule forces TCP (decision 0157).
- `codesign --deep` is deprecated and cannot sign bundled Python: sign every nested Mach-O inside out.
- `if:` expressions cannot read secrets, so they are passed as action inputs and checked inside.

## Shared files with other branches

`.github/workflows/build_orca.yml` (the hook above; also another Cosmyx task may add Windows signing hooks, check `scripts/sign_windows.ps1` references in `cosmyx-checks.yml` paths), `CHANGELOG.md`, `justfile` (existing `import? macos-signing.just`), `wiki/cosmyx/artifact-checks.md`, `.github/workflows/cosmyx-artifact-checks.yml`, `scripts/cosmyx/artifact_checks/*` and `data/expectations.json` (parent and child both edit), `wiki/decisions/0003-changelog-slots.md` and `0146-macos-arch-and-signature-checks.md` (amended here, also touched by `ci/cosmyx-exec-smoke`), `scripts/cosmyx/tests/test_foundation.py` (one-line edit, also edited by `ci/cosmyx-exec-smoke`), `scripts/cosmyx/tests/test_breaker_info_plist.py` (created here, edited by exec-smoke).
