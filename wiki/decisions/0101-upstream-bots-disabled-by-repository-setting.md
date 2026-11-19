# 0101. Upstream bots are disabled by repository setting

## Status

Accepted.

## Context

Upstream ships scheduled bots (`stale.yml`, `approve_pr_checks.yml`,
`assign.yml`, `auto-close-duplicates.yml`) that label, close or approve issues
and pull requests. On the fork they would act on our issues. Editing or
deleting these files would conflict with every upstream change to them.

## Decision

- The workflow files stay identical to upstream. The bots are disabled on the
  repository through the GitHub API (`PUT .../actions/workflows/<file>/disable`),
  which is a repository setting, not a file change.
- `.github/cosmyx/workflow-policy.json` lists them under `disable`; the sync
  applies the list on every run. A workflow already disabled, inactive
  (`assign.yml` answers 403 "not active"), or not registered yet
  (`auto-close-duplicates.yml` answers 404) is left alone and retried later.
- Every scheduled workflow must be in `disable` or `allow_scheduled`; an
  unlisted one fails the run, so a new upstream bot is never adopted silently.
- `build_all.yml` and the sync itself are in `must_stay_enabled` and are never
  disabled.

## Consequences

- Zero upstream file is touched.
- A scheduled workflow added upstream breaks the sync until someone classifies
  it, which is the point.
- Removing it: delete the policy file and the `workflow-policy` job, then
  re-enable the bots by hand if wanted (`gh workflow enable <file>`).
