# 0098. Signing settings from the existing secrets, OIDC subject by ref

## Status

Accepted. Supersedes 0091 and 0093.

## Context

The repository already holds the Azure settings of the previous Cosmyx
pipeline as secrets, not variables: `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`,
`AZURE_SUBSCRIPTION_ID`, `AZURE_TRUSTED_SIGNING_ENDPOINT`,
`AZURE_CODE_SIGNING_NAME` (the signing account) and `AZURE_CERT_PROFILE_NAME`.
It has no repository variables. A step's `if:` cannot read the `secrets`
context. The previous pipeline ran its build job in the GitHub environment
`azure-signing`, so its Entra federated credential names the subject
`repo:Cosmyx/OrcaSlicer:environment:azure-signing`.

Two ways to get an OIDC subject Azure accepts:

- (a) Add `environment: azure-signing` to the `build_orca` job. That is an edit
  to an upstream job header, next to `runs-on` and the `env:` block upstream
  edits on every Jsign or NSIS bump. The job is reusable and runs every leg
  (Linux, macOS, both Windows arches, pull requests included), so each leg would
  create a deployment record, wait on any protection rule of the environment
  (required reviewers, branch policies) and see its environment secrets. A
  branch policy on `azure-signing` would block the Linux and macOS builds of
  every other ref.
- (b) Keep the job without an environment: the subject is
  `repo:Cosmyx/OrcaSlicer:ref:refs/heads/<branch>`, and the Entra application
  gets one federated credential per signed ref. No upstream line changes; the
  cost is a one-off Azure setting per signed branch.

## Decision

- Option (b): no job environment. The federated credentials to add are listed
  in `wiki/cosmyx/windows-signing.md`.
- The setup step of `build_orca.yml` passes the six secrets to the
  `cosmyx-sign` action as inputs. The action's first step checks them: none set,
  signing is off (a notice, the `enabled` output is `false`); some set, the
  step fails and names the missing ones; all set, `enabled` is `true`. The sign
  and verify steps run on `steps.cosmyx_sign.outputs.enabled == 'true'`. No
  job-level `env` line is added to expose a secret.
- The setup step still runs only on Windows, outside the upstream repository,
  not for pull requests, not on MIXED, and on DEV or `release/*` (or every ref
  when the variable `COSMYX_SIGN_ALL_REFS` is `true`, which also needs a
  federated credential for that ref).
- Upstream's own signing steps stay skipped on our repository: their condition
  requires `github.repository == 'OrcaSlicer/OrcaSlicer'`.

## Consequences

- Without the secrets (forks) the build is unchanged and unsigned.
- A signed ref without its federated credential fails at "Log in to Azure"
  with an `AADSTS70021` "no matching federated identity record" error.
- Choosing (a) later takes one `environment:` line in the job header and an
  evaluation of that environment's protection rules.
- Removing it: delete the three `# Cosmyx` steps in `build_orca.yml` and the
  federated credentials.
