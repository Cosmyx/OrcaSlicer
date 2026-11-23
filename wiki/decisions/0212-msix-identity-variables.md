# 0212. The MSIX identity comes from repository variables

## Status

Accepted.

## Context

The MSIX package identity is not text the branding can rename: upstream's
"Build MSIX Store package Win" step passes it to `build_msix.ps1` from the
repository variables `ORCA_MSIX_IDENTITY_NAME`, `ORCA_MSIX_PUBLISHER` and
`ORCA_MSIX_PUBLISHER_DISPLAY_NAME`, with OrcaSlicer's own values as defaults.
The publisher must equal the subject of the certificate that signs the
package, which Cosmyx does not have yet. Nothing has been shipped, so no
installed identity needs migrating.

## Decision

- The Cosmyx identity is `ORCA_MSIX_IDENTITY_NAME` = `Cosmyx.CosmoSlice` and
  `ORCA_MSIX_PUBLISHER_DISPLAY_NAME` = `Cosmyx`, set as repository variables
  (Settings > Secrets and variables > Actions > Variables) by a repository
  admin. No line of the workflow changes.
- `ORCA_MSIX_PUBLISHER` stays unset, so the upstream default publisher is
  used, until the signing certificate exists; it is then set to that
  certificate's subject (`CN=...`, exactly as in the certificate).
- The display names in the manifest are CosmoSlice already (decision 0132),
  and the executable and alias follow decision 0210.

## Consequences

- Until the variables are set, a Cosmyx MSIX carries OrcaSlicer's identity
  and cannot be installed next to an upstream MSIX; it is a CI artifact only.
- Removing it: delete the variables; the upstream defaults apply.
