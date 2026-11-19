# 0096. Check our signatures by certificate subject

## Status

Accepted.

## Context

Upstream's check compares the signer's thumbprint with its release
certificate file. Artifact Signing issues a new short-lived certificate every
few days, so there is no fixed certificate or thumbprint to pin.

## Decision

- A signature is ours when its signer subject equals `COSMYX_SIGN_SUBJECT`
  exactly (as Windows prints it, for example `CN=..., O=..., C=FR`).
- `-Verify` fails on an unsigned file, on a file named directly that is not
  ours, on one of ours without a timestamp, and on any status other than
  `Valid`.
- The reuse record only copies a file that is still ours by that rule.

## Consequences

- A wrong `COSMYX_SIGN_SUBJECT` makes the verify step fail and print the
  subject actually found, which is the value to set.
