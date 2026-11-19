# Upstream sync

The fork follows upstream OrcaSlicer through three branches:

| Branch          | Content                                         | Who writes it          |
|-----------------|-------------------------------------------------|------------------------|
| `Orca-Upstream` | exact copy of `OrcaSlicer/OrcaSlicer` `main`    | the sync, force-pushed |
| `DEV`           | default branch: upstream plus the Cosmyx changes | pull requests          |
| `MIXED`         | `DEV` merged with `Orca-Upstream`               | the sync, force-pushed |

Never commit on `Orca-Upstream` or `MIXED`: both are rewritten on every run.

## What runs

`.github/workflows/cosmyx-upstream-sync.yml` runs every six hours (`23 */6 * * *`)
and on demand, one run at a time (a new run waits, it never cancels one).
Every step is a subcommand of `scripts/cosmyx/upstream_sync.py`.

1. **mirror** compares the tips of upstream `main` and `Orca-Upstream`. When
   they differ it fetches upstream into a scratch repository and force-pushes
   it, so even an upstream history rewrite is followed.
2. **mixed** merges `Orca-Upstream` into `DEV` without a working tree
   (`git merge-tree --write-tree`) and writes a commit with two parents, `DEV`
   then `Orca-Upstream`, whose message ends with the trailer
   `Cosmyx-Mixed: base=<DEV sha> upstream=<Orca-Upstream sha>`. When the
   current `MIXED` tip already carries the same trailer, nothing is pushed.
   A merge conflict lists every conflicted file in the job summary and as an
   error annotation, pushes nothing, and fails with exit code 2.
3. **dispatch** starts `build_all.yml` on `MIXED` when `MIXED` moved and prints
   the run link in the job summary.
4. **workflow-policy** checks `.github/cosmyx/workflow-policy.json` against the
   workflow files, then disables the upstream bots it lists (see below).

A conflict on `MIXED` is a bug: the fork's rule is that upstream merges into
`DEV` with zero conflicts. Fix it on `DEV` by moving the Cosmyx change out of
the upstream file, or by shrinking its hook, then let the next run rebuild
`MIXED`.

## Scheduled workflow policy

Upstream ships workflows that run on a schedule. Scheduled workflows only run
from the default branch, so on the fork they run from `DEV`. Some are upstream
issue and pull request bots that must not act on the fork.

`.github/cosmyx/workflow-policy.json` holds three lists:

- `disable`: workflows disabled on the repository through the GitHub API. A
  workflow that is already disabled, inactive, or not registered yet is left
  alone and retried on the next run, so applying the policy is idempotent.
- `allow_scheduled`: scheduled workflows that may run on the fork.
- `must_stay_enabled`: workflows the policy never disables and warns about
  when they are not active (`build_all.yml`, this sync).

Every workflow with a `schedule` trigger must be in `allow_scheduled` or in
`disable`. When upstream adds a new scheduled workflow, the next sync fails
with an annotation naming it: add it to one of the two lists in a pull request.

Event-driven upstream bots (`pr-label-bot.yml`, `pr-merge-bot.yml`,
`dedupe-issues.yml`, `backfill-duplicate-comments.yml`) are not scheduled, so
the policy does not cover them; see decision 0102.

## Token

`GITHUB_TOKEN` cannot push a commit that changes `.github/workflows/`, and
upstream changes those files often, in `Orca-Upstream` and so in `MIXED`. The
pushes use the `UPSTREAM_SYNC_TOKEN` secret: a fine-grained personal access
token on this repository only, with **Contents: read and write** and
**Workflows: read and write**. Without it the run falls back to `GITHUB_TOKEN`
with a warning and fails on such commits.

The dispatch and the policy use the job's own token (`actions: write`).

## Recipes

| Recipe                       | What it does                                           |
|------------------------------|--------------------------------------------------------|
| `just sync-mixed-dry-run`    | rebuild `MIXED` locally in a scratch repository, push nothing |
| `just workflow-policy`       | check the scheduled workflow policy                    |
| `just workflow-policy-apply` | disable the listed workflows on GitHub (needs `gh` auth) |
| `just sync-dispatch`         | start the sync workflow on `DEV` as a dry run          |
| `just sync-dispatch false`   | start a real sync run                                  |
| `just test-scripts`          | run the script tests, including this sync's            |

## Decisions

0100 to 0104 in `wiki/decisions/`.
