# Windows code signing (Azure Artifact Signing)

Cosmyx Windows builds are Authenticode-signed with Azure Artifact Signing
(formerly Trusted Signing): the portable app, the profile validator, the NSIS
plugins, the installer's payload, the uninstaller and the installer itself.
Every signature is timestamped.

## How it works

| Piece | Role |
|-------|------|
| `.github/actions/cosmyx-sign/action.yml` | `setup`, `sign` and `verify` modes, called from three `# Cosmyx` steps in `build_orca.yml`. |
| `scripts/cosmyx/sign_windows_azure.ps1` | Signs with Jsign (`--storetype TRUSTEDSIGNING`), or checks the signatures with `-Verify`. |
| `scripts/sign_windows.ps1` | Upstream's script; one `# Cosmyx` line hands over to ours when `COSMYX_SIGN_BACKEND` is `azure`. |
| `CMakeLists.txt` (upstream, unchanged) | Wires `scripts/sign_windows.ps1` into the NSIS build when `ORCA_SIGN_KMS_KEY` is defined; `setup` sets it to the sentinel `cosmyx-azure`. |

The build steps, in order:

1. `setup` (before "Build slicer Win"): downloads upstream's pinned Jsign, sets
   up Java, exports `COSMYX_SIGN_*`, `ORCA_SIGN_JSIGN` and the CMake sentinel.
2. `sign` (after the build, before the installer): Azure login with OIDC, an
   access token exported masked as `COSMYX_SIGN_TOKEN`, then signs the shipped
   files. The background cpack reuses them and signs the uninstaller and the
   installer.
3. `verify` (after the installer): checks every file, the installer, its
   payload and the uninstaller a silent install writes.

Builds that are signed: DEV and `release/*`, never pull requests or MIXED
(decision 0093). `build_all` does not run on DEV pushes; start it by hand with
`just build-all DEV`.

## What to set up in Azure

1. An Artifact Signing account and a certificate profile (public trust), with
   its identity validation done. Note the account's region endpoint, for
   example `https://weu.codesigning.azure.net/` (it must match the account's
   region).
2. An Entra application registration (or a user-assigned managed identity) for
   GitHub Actions.
3. On that application, one federated credential per signed ref:
   - Issuer `https://token.actions.githubusercontent.com`
   - Audience `api://AzureADTokenExchange`
   - Subject `repo:Cosmyx/OrcaSlicer:ref:refs/heads/DEV`
   - Subject `repo:Cosmyx/OrcaSlicer:ref:refs/heads/release/<name>`, one per
     release branch, or a single flexible federated credential matching
     `repo:Cosmyx/OrcaSlicer:ref:refs/heads/release/*`.
   - Any feature branch tested with `COSMYX_SIGN_ALL_REFS` needs its own
     subject too.
4. A role assignment: "Artifact Signing Certificate Profile Signer" for that
   application, on the certificate profile (or the signing account).

## What to set in GitHub

Repository variables (Settings, Secrets and variables, Actions, Variables). No
secret is needed.

| Variable | Value |
|----------|-------|
| `COSMYX_AZURE_CLIENT_ID` | Application (client) ID of the Entra application. |
| `COSMYX_AZURE_TENANT_ID` | Directory (tenant) ID. |
| `COSMYX_AZURE_SUBSCRIPTION_ID` | Subscription that holds the signing account. |
| `COSMYX_SIGN_ENDPOINT` | Account endpoint, for example `https://weu.codesigning.azure.net/`. |
| `COSMYX_SIGN_ACCOUNT` | Signing account name. Signing is off while it is empty. |
| `COSMYX_SIGN_PROFILE` | Certificate profile name. |
| `COSMYX_SIGN_SUBJECT` | Certificate subject as Windows prints it, for example `CN=Cosmyx, O=Cosmyx, L=City, C=FR`. If the first verify fails with "signed by ..., not ...", the subject it prints is the value to set. |
| `COSMYX_SIGN_ALL_REFS` | Optional. `true` signs every non-PR, non-MIXED ref (for tests). |

## Checking locally

- `just test-scripts` runs the Pester tests of the script (when `pwsh` is
  installed).
- `just sign-dryrun <path>` prints the Jsign command and the files that would
  be signed. It needs `COSMYX_SIGN_ENDPOINT`, `COSMYX_SIGN_ACCOUNT`,
  `COSMYX_SIGN_PROFILE` and `ORCA_SIGN_JSIGN` in the environment (any values).

## Decisions

0090 Jsign backend, 0091 OIDC per ref, 0092 token resource, 0093 signed refs,
0094 token lifetime, 0095 upstream hooks, 0096 verify by subject, 0097 tests.
