# 0092. Access token resource for Artifact Signing

## Status

Accepted.

## Context

Jsign takes the access token as its store password. Its documentation does not
state the resource the token must be issued for. `https://codesigning.azure.net`
is the audience the Azure SDK client uses, but it was not confirmed against
Jsign at the time of writing.

## Decision

- The token is requested for `https://codesigning.azure.net`.
- `COSMYX_SIGN_RESOURCE` (an environment variable, empty by default) overrides
  it without a code change, both for the first token and for a refresh.
- Fallback if Jsign cannot sign with such a token: Microsoft's signtool with
  the Artifact Signing dlib on x64, which would leave arm64 builds unsigned. It
  is not implemented.

## Consequences

- The first signed run on DEV confirms or refutes the resource; a 401 or 403
  from Jsign is the symptom.
