# macOS signing

DEV and `release/*` builds of the universal macOS app are signed with the
Cosmyx Developer ID Application certificate, notarised by Apple and stapled,
so Gatekeeper opens them without a warning. The DMGs keep their usual names.
Decisions 0150 to 0158.

## How it runs

`build_orca.yml` has one `# Cosmyx` step, "Cosmyx sign and notarize macOS",
right after "Create DMG without notary" on the macOS combine leg. It calls
`.github/actions/cosmyx-sign-macos`, which:

1. checks the seven Apple secrets (none: off with a notice; some: fails and
   names the missing ones);
2. imports the certificate into a temporary keychain and checks it holds a
   `Developer ID Application:` identity matching `MACOS_CERTIFICATE_ID`;
3. on GitHub-hosted runners, blocks UDP 443 with pf so `stapler` uses TCP;
4. runs `scripts/cosmyx/macos_signing/cli.py run`:
   - signs every Mach-O file and nested bundle of each `.app` in
     `build/universal/OrcaSlicer/`, inside out, with the hardened runtime, a
     secure timestamp and `scripts/disable_validation.entitlements`, then the
     app (never `--deep`);
   - notarises the apps (zipped), staples them;
   - rebuilds `OrcaSlicer_Mac_universal_<ver>.dmg` and
     `OrcaSlicer_profile_validator_Mac_universal_<ver>.dmg` from the stapled
     apps with upstream's `create_dmg`, signs, notarises and staples them;
   - verifies everything (below) and writes a step summary;
5. on failure, uploads the notary logs as `cosmyx-notary-log-<ver>`;
6. always deletes the keychain, restores the keychain list and releases pf.

The step runs when the signing predicate of decision 0098 holds: not the
upstream repository, not a pull request, not MIXED, on DEV or `release/*`, or
on every ref when the variable `COSMYX_SIGN_ALL_REFS` is `true`. Pull
requests and other refs keep the ad-hoc DMG.

## Settings

Repository secrets (Settings, Secrets and variables, Actions), the same names
upstream uses:

| Secret | Content |
|--------|---------|
| `BUILD_CERTIFICATE_BASE64` | The Developer ID Application certificate with its private key, exported as `.p12`, in base64 (`base64 -i cert.p12`). |
| `P12_PASSWORD` | The `.p12` export password. |
| `KEYCHAIN_PASSWORD` | Any strong password; it only protects the temporary keychain. |
| `MACOS_CERTIFICATE_ID` | The codesign identity: the certificate's SHA-1 or its full name, `Developer ID Application: <name> (<team>)`. |
| `APPLE_DEV_ACCOUNT` | The Apple ID that notarises. |
| `APP_PWD` | An app-specific password of that Apple ID (appleid.apple.com, Sign-In and Security). |
| `TEAM_ID` | The 10-character Apple team ID. |

The variable `SELF_HOSTED` (non-empty on self-hosted runners) skips the pf
rule. No secret is ever printed: GitHub masks them, and the script redacts
them from its own messages and logs.

## What is verified

The step fails when any of these does not hold (decision 0155):

- `codesign --verify --deep --strict` on each app;
- for every Mach-O file and nested bundle: a `Developer ID Application:`
  authority, the `TEAM_ID` team, the hardened runtime, a secure timestamp and
  no `get-task-allow` entitlement;
- `spctl -t exec` sees a notarised Developer ID app, `stapler validate`
  passes, and `syspolicy_check distribution` passes where it exists;
- each DMG is stapled and `spctl -t open --context
  context:primary-signature` accepts it.

The artifact checks repeat the essential rules on the uploaded DMG (see
`wiki/cosmyx/artifact-checks.md`).

## When it fails

| Message | Cause and fix |
|---------|---------------|
| `macOS signing needs these secrets too: ...` | Some secrets are missing: add them, or remove all seven to turn signing off. |
| `not a Developer ID Application certificate` | The `.p12` holds another certificate type (Apple Development, Mac App Distribution...): export the Developer ID Application one. |
| `MACOS_CERTIFICATE_ID matches no signing identity` | Use the SHA-1 or the exact name `security find-identity -v -p codesigning` prints for the certificate. |
| `notarytool submit ... failed` with an authentication error | The app-specific password expired or was revoked: create a new one and update `APP_PWD`. |
| `Notarisation of ... was Invalid` | Read the issues in the step summary or the `cosmyx-notary-log-<ver>` artifact (an unsigned or unstamped file, usually). |
| `stapler staple ... failed after 5 attempts` | Apple's CDN was slow: rerun the job. |

## Running it

- `just mac-sign-dryrun <path to an .app>` (macOS) signs a copy of a local app
  ad-hoc in the CI's order and verifies it; the app itself is not changed.
- `just mac-sign-status [branch]` lists the signing step's result in the
  latest "Build all" runs (needs `gh`).
- `just test-scripts` runs `test_macos_signing.py` (fake runner everywhere,
  real ad-hoc signing on macOS with `cc`) and `test_macos_signing_wiring.py`.

## Removing it

Delete the "Cosmyx sign and notarize macOS" step of `build_orca.yml`, the
action, `scripts/cosmyx/macos_signing/`, its tests and recipes. The build then
ships ad-hoc signed DMGs again.
