# 0094. Access token lifetime against the installer build

## Status

Accepted.

## Context

An Azure access token lasts about an hour. The installer is built by cpack in
the background ("Start installer Win" to "Finish installer Win", up to 30
minutes) and signs the uninstaller and the installer at the very end of the
makensis run. The GitHub OIDC assertion behind the Azure CLI login may have
expired by then.

## Decision

- The token is taken in the `sign` mode, after the build and right before the
  installer starts, like upstream's Google Cloud token.
- Its expiry (`expires_on`) is exported as `COSMYX_SIGN_TOKEN_EXPIRES`. Within
  five minutes of it, the script asks the Azure CLI for a new token; if that
  fails it stops with "COSMYX_SIGN_TOKEN has expired and could not be
  refreshed", instead of an opaque Jsign error.

## Consequences

- A normal run (signing a few minutes, cpack under 30) stays inside the hour.
- If timeouts appear, a fourth step re-running the `sign` mode's token request
  before "Start installer Win" is the next move.
