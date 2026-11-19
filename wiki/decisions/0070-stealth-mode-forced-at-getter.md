# 0070. Stealth mode forced at the getter

## Status

Accepted.

## Context

Cosmyx builds must never reach the Orca or Bambu clouds: no login, no profile
sync, no vendor update query, no device or HMS service. Upstream gates all of
these on `AppConfig::get_stealth_mode()`, which returns true only until the
setup guide is finished and then follows the `stealth_mode` setting, which
defaults to false and can be turned off from the guide, from Preferences and
from the "Quit Stealth Mode" button of the login dialog.

The old fork forced the default in `AppConfig::set_defaults()` and in the
guide. That left the user able to turn it off again, and needed several hooks.
Re-forcing the value after each writer (guide `SaveProfile()`, login dialog)
would also need one hook per writer.

## Decision

- The first statement of `AppConfig::get_stealth_mode()` is
  `return true; // Cosmyx: stealth mode forced on (decision 0070)`.
- Every reader of stealth mode goes through that getter, so one line in
  libslic3r covers them all, whatever the stored `stealth_mode` value is.
- The stored setting is left as it is: it is still written by the guide,
  Preferences and the login dialog, and simply ignored.
- `cosmyx_tests` checks that the getter returns true with the guide finished
  and `stealth_mode` stored as false, true or missing.

## Consequences

- The upstream code after the hook is unreachable but kept, so the hunk is a
  single added line and merges of upstream stay conflict-free.
- A future upstream reader that calls `get_bool("stealth_mode")` directly
  would bypass the hook; `git grep stealth_mode` after each upstream sync
  catches it.
- Removing it: delete the hook line in `src/libslic3r/AppConfig.cpp` and the
  getter checks in `tests/cosmyx/test_cosmyx_stealth.cpp`.
