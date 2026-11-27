# 0200. Stealth mode on until the user opts out

## Status

Accepted. Supersedes 0070 and 0071.

## Context

Decision 0070 forced `AppConfig::get_stealth_mode()` to return true, which
kept every cloud feature off for good. Cosmyx now has its own cloud,
CosmoCloud (decision 0201), so users must be able to leave stealth mode again,
while a new install still starts in it.

Upstream `AppConfig::set_defaults()` stores `stealth_mode` as false when it is
missing, so the stored value of a fresh configuration cannot tell the upstream
default from a user choice.

## Decision

- The T7 hook line keeps its place as the first statement of
  `get_stealth_mode()`, and now reads
  `return Cosmyx::stealth_mode(*this); // Cosmyx: on until the user opts out (decision 0200)`.
  `AppConfig.cpp` also gets `#include "Cosmyx/StealthMode.hpp" // Cosmyx` right
  after `#include "AppConfig.hpp"`, not after the first include as decision
  0002 says, because `feat/cosmyx-dark-default` already adds its include
  there and the two Cosmyx branches would conflict.
- `Cosmyx::stealth_mode()` (`src/libslic3r/Cosmyx/StealthMode.cpp`) keeps the
  upstream rule (on until the setup guide is finished), then returns the
  stored `stealth_mode` once the configuration is seeded, and
  `STEALTH_MODE_DEFAULT` before that. It only reads the configuration.
- The default is one constant, `Cosmyx::STEALTH_MODE_DEFAULT = true`.
- `Cosmyx::seed_stealth_mode()` writes the default to `stealth_mode` once per
  configuration and sets the app key `cosmyx_stealth_mode_seeded`. It runs at
  every start from `apply_cloud_server()` (decision 0201), before the cloud
  agent is created; from the second start on it writes nothing, so a user's
  choice survives.
- The Preferences checkbox and the "Quit Stealth Mode" button of the login
  dialog work again, as upstream: they write `stealth_mode`, which the getter
  now follows.
- The setup guide policy (decision 0073) still finishes the guide in stealth
  mode. Running the guide again therefore turns stealth mode back on; the user
  turns it off again from Preferences. This errs on the side of privacy.

## Consequences

- A new install, and an install upgraded from a forced-stealth build, start in
  stealth mode once; from then on the user decides.
- Decision 0072 still describes what stealth mode blocks while it is on.
- `cosmyx_tests` (`test_cosmyx_stealth.cpp`) checks the getter before the
  guide, before and after seeding, the opt-out and the opt-in;
  `scripts/cosmyx/tests/test_cloud_server.py` pins the hook lines.
- Removing it: put back the 0070 line, delete `StealthMode.{hpp,cpp}`, the
  include line and the seeding call in `CloudServer.cpp`.
