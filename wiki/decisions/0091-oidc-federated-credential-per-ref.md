# 0091. Azure login with OIDC, one federated credential per signed ref

## Status

Superseded by 0098.

## Context

The build must reach the Artifact Signing account without a stored secret.
`build_all.yml` already grants `id-token: write` to the Windows job (upstream
uses it for Google Cloud), and the Windows job has no GitHub environment, so the
OIDC token subject is `repo:<owner>/<repo>:ref:refs/heads/<branch>`.

## Decision

- The `sign` mode logs in with `azure/login@v3` (client ID, tenant ID,
  subscription ID from repository variables), then asks the Azure CLI for an
  access token to the Artifact Signing resource.
- No GitHub environment is added to the upstream job (that would be a larger
  upstream edit). The Entra application therefore needs one federated
  credential per signed ref: `refs/heads/DEV`, and each `release/*` branch
  (or one flexible federated credential matching `refs/heads/release/*`).
- The application gets the role "Artifact Signing Certificate Profile Signer"
  on the certificate profile (or the account), nothing more.

## Consequences

- A new release branch is not signed until its credential exists: the login
  step fails with a clear Azure error.
- Removing it: delete the federated credentials and the role assignment.
