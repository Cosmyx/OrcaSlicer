# 0202. CosmoCloud public key placeholder

## Status

Accepted.

## Context

The cloud agent sends `orca_pub_key` as the `apikey` header of every call. The
key is public, not a secret, but the production value of CosmoCloud is not
known yet. A CosmoCloud server started without configuration accepts
`cosmocloud-public-key`.

## Decision

- `CLOUD_PUB_KEY` in `src/slic3r/GUI/Cosmyx/logic/CloudServer.hpp` is the one
  place the key is written, set to the placeholder `cosmocloud-public-key`.
- A release build must replace it with the production key first. This is a
  release step, checked at warning level:
  `scripts/cosmyx/tests/test_cloud_server.py` warns while the constant is the
  placeholder, so `just test-scripts` and the checks workflow show it without
  failing development builds.
- A build-breaking check was not added: there is no release-only switch in the
  build yet, and a failing check would block every development build.

## Consequences

- Development builds work against a default CosmoCloud.
- A release made without the replacement fails at sign-in against a
  production CosmoCloud, it does not leak anything.
- Removing it: put the production key in `CLOUD_PUB_KEY` and drop the warning
  test.
