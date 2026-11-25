# 0103. Scheduled workflows and the 60-day auto-disable

## Status

Accepted.

## Context

GitHub disables the scheduled workflows of a public repository after 60 days
without repository activity. The sync is scheduled, so it could stop itself on
a quiet fork, and with it the guard of decision 0100.

## Decision

- No keep-alive commit is added. Each run that moves `Orca-Upstream` or
  `MIXED` pushes to the repository, and upstream moves far more often than
  every 60 days, which keeps the repository active.
- The sync and `build_all.yml` are in `must_stay_enabled`: the policy job
  prints a warning annotation when one of them is not active, so a disabled
  state is visible in the run, and `gh workflow enable <file>` brings it back.

## Consequences

- If upstream stalls for 60 days the schedule can be disabled; the warning
  appears only on a run started by hand. Re-enabling is one command.
- Nothing to remove beyond decision 0100.
