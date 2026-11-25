# 0102. Event-driven upstream bots are left to the user

## Status

Accepted.

## Context

Besides the scheduled bots, upstream has bots triggered by issue and pull
request events: `pr-label-bot.yml`, `pr-merge-bot.yml`, `dedupe-issues.yml` and
`backfill-duplicate-comments.yml`. They are not scheduled, so the policy of
decision 0101 does not see them, and whether they help or hurt on the fork
depends on how the fork uses issues and pull requests.

## Decision

The sync does not touch them. They are listed in `wiki/cosmyx/upstream-sync.md`
for the user to decide; disabling one is a repository setting
(`gh workflow disable <file>`), and adding it to the `disable` list of the
policy keeps it disabled.

## Consequences

- Until the user decides, these bots may run on fork events, and may fail for
  lack of the secrets upstream gives them.
- Nothing to remove: this decision adds no code.
