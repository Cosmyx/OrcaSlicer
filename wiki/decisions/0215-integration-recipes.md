# 0215. Integration and rebase-check recipes

## Status

Accepted.

## Context

Every Cosmyx feature lives on its own pull request branch, stacked on the
foundation (#86) and sometimes on another feature. Two jobs come back often:

- rebuilding `ci/cosmyx-integration` (DEV plus every open pull request branch,
  merged in a fixed order) to build them together;
- rebasing every branch onto a new upstream release tag.

Most of their conflicts are always the same kinds: sibling branches adding
their own changelog slot and slot-list entries at the same place, generated
branding review tables rewritten by two branches, and resolutions already
recorded once. Resolving those by hand each time is slow and error-prone, and
it hides the conflicts that really need a person or an agent.

## Decision

- `scripts/cosmyx/integrate/cli.py` (standard library only, called by the
  recipes in `scripts/cosmyx/just/integrate.just`):
  - `just cosmo-integrate [BASE]` resets `ci/cosmyx-integration` to BASE
    (default `origin/DEV`) in the worktree `.worktrees/integration` (created,
    or reused only when clean), and merges `origin/<branch>` with `--no-ff` for
    every row of the branch list. It pushes nothing unless `--push`, which
    uses `--force-with-lease` on the remote tip seen at the start; `--build`
    then starts `build_all.yml` on the branch.
  - `just cosmo-rebase-check TAG` replays, in a temporary worktree outside the
    repository, each branch's own commits (those after its merge base with its
    parent, the foundation for a `DEV`-parented branch) onto
    `refs/tags/upstream/TAG` (fetched from upstream when missing), stacked
    children onto their replayed parent. It creates and moves no branch and
    always removes the temporary worktree. An unknown conflict is reported,
    then overridden with the branch's side only to keep going, and the
    branches stacked on it are marked approximate.
- Known conflict kinds, resolved inside the merge (or cherry-pick) commit:
  - `CHANGELOG.md`: union of the slot blocks, ours first, then the blocks only
    the merged branch has; for a marker both sides carry, the merged branch's
    extra entries go above (newest first).
  - `SLOTS_BY_AREA` in `scripts/cosmyx/tests/test_foundation.py` and the slot
    list of decision 0003: union of the slots, ordered by the marker order of
    the resolved `CHANGELOG.md`.
  - Branding manifests and review tables: one side is taken (ours, then
    theirs), the branch's own branding engine runs `sync` and `render`, and
    the side is kept only when no row `validated` on either side lost that
    status.
  - Anything `rerere` resolves. rerere is on for the run, and
    `cosmo-integrate` first teaches it the resolutions of the merges of the
    current `origin/ci/cosmyx-integration` (as git's contrib `rerere-train`
    does), so a fresh clone replays them too; `--train REF` picks another
    reference, `--no-train` skips it. Merges use the default conflict style so
    that rerere finds resolutions recorded by hand merges.
  - A resolver accepts a hunk only when both sides purely added to the base;
    anything else is an unknown conflict.
- Any other conflict aborts that merge and stops with the branch, the files
  and a summary of their hunks, exit code 1.
- The branch list and order are data, `scripts/cosmyx/integrate/branches.json`
  (name, pull request, parent, `integration_only` for the rebase skill branch),
  not parsed from the rebase skill's `branches.md`: that file lives on a docs
  branch, is prose for agents, and is not in the trees the recipes run on. A
  new pull request branch is one new row, after its parent. The rebase skill
  points to this file and keeps its table in the same order.
- The root `justfile` is owned by the foundation. This change adds one
  `import? 'scripts/cosmyx/just/integrate.just'` line, in alphabetical place,
  like the other feature recipe files.

## Consequences

- An agent only handles the conflicts the recipes cannot: the stop report
  names them.
- `ci/cosmyx-integration` stays a throwaway branch; the local branch is reset
  on every run.
- The branch list must be kept in step with the open pull requests.
- Removing it: delete `scripts/cosmyx/integrate/`,
  `scripts/cosmyx/just/integrate.just`, `scripts/cosmyx/tests/test_integrate_*.py`,
  the justfile import line, the T20 slot (changelog, `SLOTS_BY_AREA`, decision
  0003) and this decision; integration and rebases then go back to being done
  by hand.
