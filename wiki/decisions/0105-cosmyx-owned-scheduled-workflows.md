# 0105. Cosmyx-owned scheduled workflows need no policy entry

## Status

Accepted.

## Context

The workflow policy (`.github/cosmyx/workflow-policy.json`) fails the sync when
a scheduled workflow is in neither `allow_scheduled` nor `disable`. Its purpose
is to catch new scheduled workflows that upstream adds. Cosmyx branches also
add scheduled workflows of their own (for example the weekly GUI goldens run).
Making each of them add an entry to the policy file would have every such pull
request edit the same lists, and the branches would conflict with each other.

## Decision

- The policy has a `cosmyx_owned_glob` key, `cosmyx-*.yml` by default, matched
  case-sensitively against the workflow file name. Our workflows already use
  that prefix, and upstream has no file with it.
- A scheduled workflow matching the glob is allowed without an entry.
- A matching workflow is never disabled: listing it in `disable` fails the
  check, and the apply step skips it even if the check was bypassed.
- `must_stay_enabled` is unchanged and may still name Cosmyx-owned workflows
  (the sync itself is listed there).

## Consequences

- A Cosmyx workflow named without the prefix still needs an entry, and an
  upstream file that ever used the prefix would slip through the guard; both
  are unlikely and visible in review.
- Removing this: drop the key and the `is_owned` checks in
  `scripts/cosmyx/upstream_sync.py`, then list every scheduled `cosmyx-*.yml`
  workflow in `allow_scheduled`.
