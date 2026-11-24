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
  - `just cosmo-integrate [BASE]` resets the integration branch to BASE
    (default `origin/DEV`) in its worktree (created, or reused only when
    clean), and merges `origin/<branch>` with `--no-ff` for
    every row of the branch list; a row not on the remote yet is skipped with
    a warning. It pushes nothing unless `--push`, which pushes, in one atomic
    push, the branch and `cosmyx-ci/<BASE>` set to BASE's commit (`cosmyx-ci/DEV`
    for `origin/DEV`, `cosmyx-ci/v2.5.2` for the tag `v2.5.2`), each with
    `--force-with-lease` on the remote tip seen at the start.
  - The integration branch depends on BASE: the list's base (DEV) keeps
    `ci/cosmyx-integration` in `.worktrees/integration`; any other base gets
    `integration/<BASE>` in `.worktrees/integration-<BASE>` (`/` replaced by
    `-`), the name the hand-made release integrations already used
    (`integration/v2.5.2`). The DEV integration and a release integration
    therefore coexist, each with its own branch, worktree, base branch and
    build pull request. `--branch` and `--worktree` override the defaults.
    When the integration branch is already checked out in another worktree
    (a hand-made integration's, such as `.worktrees/rebase-v2.5.2/integration`),
    that worktree is used, under the same rule (only when clean); with an
    explicit `--worktree` elsewhere it stops and names the holder. Git refuses
    a branch checked out twice, and reusing a clean worktree loses nothing,
    while failing would force a person to remove it by hand on every run.
  - On a base other than the list's (a release tag), merging the DEV-based
    branches would drag in every DEV commit the base lacks (310 upstream
    commits and 76 conflicting files for `v2.5.2`). There, each branch's own
    commits (the same set `cosmo-rebase-check` replays) are first
    cherry-picked onto BASE, stacked children onto their replayed parent, as
    the local branch `rebase/<BASE>/<branch>`; then those branches are merged
    with `--no-ff` in list order, giving the layout of the hand-made release
    integrations (`Merge branch 'rebase/v2.5.2/<branch>' into
    integration/v2.5.2`). A `rebase/` branch checked out in a worktree is
    moved there only when that worktree is clean (the run stops naming it
    otherwise). Replayed commits carry the `cherry-pick -x` line naming the
    branch's original commit. An unknown conflict during the replay is first
    settled by an earlier replay of that same original commit, looked up by
    that line in the worktree's HEAD, the local `rebase/<BASE>/*` branches,
    then the remote integration branch of that base. Otherwise the run stops
    with the cherry-pick left in progress: a person resolves it in place,
    commits it with `cherry-pick --continue`, and runs again; the run reuses
    that commit, and every later run finds it in the pushed integration. This
    is rerere at the scale of a commit, needed because a release base can
    differ in ways rerere cannot record: a file the branch edits may not
    exist there (modify/delete, such as `build_flatpak.yml`, whose jobs
    still live in `build_all.yml` on `v2.5.2`), and a resolution may have to
    change files that did not conflict (a test reading the moved file).
    Matching the original commit's sha, not its subject, means a branch
    commit rewritten since gets no stale resolution. The `rebase/` branches are not pushed:
    they are throwaway and rebuilt on every run, and their commits already
    reach the remote as the second parents of the integration merges.
  - `--build` builds the integration through a draft pull request from the
    branch into `cosmyx-ci/<BASE>`, titled `ci: integration build on <BASE>
    (never merge)`, which is never merged: `build_all.yml` runs on pull
    requests to `cosmyx-ci/**`, in upstream pull request mode (macOS arm64
    and its DMG only). An open one is reused, and the push starts its run;
    otherwise it is created after the push, and its opening starts the run.
    Open build pull requests whose head is that same branch, into another
    `cosmyx-ci/` base, are closed before the push, so that the branch builds
    only on its current base; build pull requests of other integration
    branches are never touched. The
    recipe prints the pull request link and the `gh run list` command that
    finds the run. A pull request, not `workflow_dispatch`, because the run
    then has a base to diff against and shows on the pull request, like the
    upstream pull request builds it reproduces.
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
    current remote integration branch of that base (as git's contrib
    `rerere-train` does), so a fresh clone replays them too; `--train REF` picks another
    reference, `--no-train` skips it. Merges use the default conflict style so
    that rerere finds resolutions recorded by hand merges.
  - A resolver accepts a hunk only when both sides purely added to the base;
    anything else is an unknown conflict.
- Any other conflict aborts that merge (a replay's cherry-pick stays in
  progress, see above) and stops with the branch, the files and a summary of
  their hunks, exit code 1.
- The branch list and order are data, `scripts/cosmyx/integrate/branches.json`
  (name, pull request, parent, `integration_only` for the rebase skill branch),
  not parsed from the rebase skill's `branches.md`: that file lives on a docs
  branch, is prose for agents, and is not in the trees the recipes run on. A
  new pull request branch is one new row, after its parent, even before it is
  pushed. The rebase skill points to this file and keeps its table in the
  same order.
- The root `justfile` is owned by the foundation. This change adds one
  `import? 'scripts/cosmyx/just/integrate.just'` line, in alphabetical place,
  like the other feature recipe files.

## Consequences

- An agent only handles the conflicts the recipes cannot: the stop report
  names them.
- `ci/cosmyx-integration`, `integration/<BASE>` and the local
  `rebase/<BASE>/*` branches stay throwaway branches, reset on every run. The `cosmyx-ci/*` branches and the draft build pull requests
  are throwaway too: they only mark a base commit and carry the run.
- The branch list must be kept in step with the open pull requests.
- Removing it: delete `scripts/cosmyx/integrate/`,
  `scripts/cosmyx/just/integrate.just`, `scripts/cosmyx/tests/test_integrate_*.py`,
  the justfile import line, the T20 slot (changelog, `SLOTS_BY_AREA`, decision
  0003) and this decision, then close the build pull requests and delete the
  `cosmyx-ci/*` branches; integration and rebases then go back to being done
  by hand.
