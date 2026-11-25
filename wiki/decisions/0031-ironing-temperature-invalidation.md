# 0031. What a change of the ironing temperature invalidates

## Status

Accepted.

## Context

`Print::apply()` diffs two things: the static `PrintConfig` keys
(`print_diff`, which goes through `Print::invalidate_state_by_config_options()`)
and the whole full config (`full_config_diff`). The plan expected the option to
reach the "unknown key, invalidate all steps" branch of
`invalidate_state_by_config_options()`.

## Decision

Nothing to add. The option is not a `PrintConfig` member, so it never appears
in `print_diff`; it appears in `full_config_diff` only, which invalidates
`psGCodeExport` and refreshes `m_full_print_config`. A change of the ironing
temperature therefore only regenerates the G-code, which is exactly what it
affects.

## Consequences

- No hook in `Print.cpp` or `PrintApply.cpp`.
- If upstream ever stops refreshing `m_full_print_config` on a full config
  diff, the G-code would keep the old value; the G-code tests would not see it
  (they slice once), so this is worth re-checking when PrintApply.cpp changes
  a lot.
