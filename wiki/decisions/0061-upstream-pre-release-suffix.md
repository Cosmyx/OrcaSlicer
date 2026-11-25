# 0061. Upstream pre-release suffix is kept

## Status

Accepted.

## Context

On the development branch `SoftFever_VERSION` is a pre-release such as
`2.6.0-dev`; upstream releases are `2.6.0`, and its betas `2.6.0-beta`. The
display version could either keep that suffix (`2.6.0-dev-8`) or strip it
(`2.6.0-8`).

## Decision

Keep it: the display version is always `SoftFever_VERSION`, unchanged,
followed by `-<Cosmyx patch>`. `2.6.0-dev` with patch 8 gives `2.6.0-dev-8`;
a release base gives `2.6.0-8`.

## Consequences

- A build made on a development base never looks like it was made on the
  `2.6.0` release, which it is not.
- One rule, with no parsing of the upstream version: the C++ helper and the
  script just append, and cannot disagree on what to strip.
- The string stays a valid semver (`2.6.0-dev-8` is the pre-release `dev-8`).
- Changing to stripping later means changing `compose_display_version()` in
  both the C++ helper and `scripts/cosmyx/cosmyx_version.py`, and their tests.
