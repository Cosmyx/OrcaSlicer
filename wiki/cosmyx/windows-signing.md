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

Builds that are signed: DEV and `release/*`, never pull requests or MIXED,
and only when the `AZURE_*` signing secrets are set (decision 0098).
`build_all` does not run on DEV pushes; start it by hand with
`just build-all DEV`.

## What to set in GitHub

Repository secrets (Settings, Secrets and variables, Actions, Secrets). These
are the ones the previous Cosmyx pipeline already used, so they are in place.
With none of them set, the build runs unsigned; with only some, the setup step
fails and names the missing ones.

| Secret | Value |
|--------|-------|
| `AZURE_CLIENT_ID` | Application (client) ID of the Entra application. |
| `AZURE_TENANT_ID` | Directory (tenant) ID. |
| `AZURE_SUBSCRIPTION_ID` | Subscription that holds the signing account. |
| `AZURE_TRUSTED_SIGNING_ENDPOINT` | Account endpoint, for example `https://weu.codesigning.azure.net/`. |
| `AZURE_CODE_SIGNING_NAME` | Artifact Signing account name. |
| `AZURE_CERT_PROFILE_NAME` | Certificate profile name. |

Optional repository variables (Variables tab), none needed to sign:

| Variable | Value |
|----------|-------|
| `COSMYX_SIGN_EKU` | Pin: the EKU of our identity validation, `1.3.6.1.4.1.311.97.<...>` (not `.97.1.0`). Stable across certificate renewals; preferred. |
| `COSMYX_SIGN_SUBJECT` | Pin: the certificate subject as Windows prints it, for example `CN=Cosmyx, O=Cosmyx, L=City, C=FR`. |
| `COSMYX_SIGN_ALL_REFS` | `true` signs every non-PR, non-MIXED ref (for tests; each ref needs its federated credential). |

Without pins, the verify step accepts any Artifact Signing certificate
(decision 0099). Each run prints `Signer of the files named directly: Subject
'...', EKU ...` in "Cosmyx verify Windows signatures": copy the
`1.3.6.1.4.1.311.97.` EKU other than `.97.1.0` into `COSMYX_SIGN_EKU`, or the
subject into `COSMYX_SIGN_SUBJECT`.

## What to set up in Azure

The account, the certificate profile, the Entra application and its role come
from the previous pipeline. What changes is the OIDC subject: the build job has
no GitHub environment any more (decision 0098), so the federated credential
for `environment:azure-signing` no longer matches.

1. In Entra ID, open the application whose client ID is `AZURE_CLIENT_ID`,
   then Certificates & secrets, Federated credentials, Add credential, scenario
   "GitHub Actions deploying Azure resources":
   - Organization `Cosmyx`, repository `OrcaSlicer`, entity type Branch,
     branch `DEV`. That gives:
     - Issuer `https://token.actions.githubusercontent.com`
     - Subject `repo:Cosmyx/OrcaSlicer:ref:refs/heads/DEV`
     - Audience `api://AzureADTokenExchange`
   - The same for each release branch, for example branch `release/2.4`
     (subject `repo:Cosmyx/OrcaSlicer:ref:refs/heads/release/2.4`). Entra
     does not match wildcards in a plain federated credential; a flexible
     federated credential matching `repo:Cosmyx/OrcaSlicer:ref:refs/heads/release/*`
     can replace them where the tenant offers it. An application holds at most
     20 federated credentials.
   - Any branch tested with `COSMYX_SIGN_ALL_REFS` needs its own credential.
   - The `environment:azure-signing` credential can stay; nothing uses it.
2. Check that the application still has the role "Artifact Signing
   Certificate Profile Signer" (formerly "Trusted Signing Certificate Profile
   Signer") on the certificate profile or the signing account.
3. If the repository customised its OIDC subject template
   (`gh api repos/Cosmyx/OrcaSlicer/actions/oidc/customization/sub` shows
   `use_default: false`), the subject follows that template instead.

## Checking locally

- `just test-scripts` runs the Pester tests of the script (when `pwsh` is
  installed) and the checks of the workflow and action wiring.
- `just sign-dryrun <path>` prints the Jsign command and the files that would
  be signed. It needs `COSMYX_SIGN_ENDPOINT`, `COSMYX_SIGN_ACCOUNT`,
  `COSMYX_SIGN_PROFILE` and `ORCA_SIGN_JSIGN` in the environment (any values).

## Decisions

0090 Jsign backend, 0092 token resource, 0094 token lifetime, 0095 upstream
hooks, 0097 tests, 0098 settings from secrets and OIDC by ref (supersedes 0091
and 0093), 0099 verify by Artifact Signing EKU (supersedes 0096).
