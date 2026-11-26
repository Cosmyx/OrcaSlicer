---
name: cosmyx-rebase
description: Use when rebasing the Cosmyx / CosmoSlice feature branches of the Cosmyx/OrcaSlicer fork onto a new upstream OrcaSlicer release or tag, when rebuilding CosmoSlice on a new upstream OrcaSlicer version (finding the latest upstream release, replaying every Cosmyx branch, fixing conflicts and compile breaks, assembling and building an integration branch, writing the rebase report), or when updating the rebase feature sheets, branches.md or conflits.md after such a pass.
---

# Cosmyx rebase onto an upstream OrcaSlicer release

One agent, alone, no subagents. You replay the ~25 Cosmyx feature branches on the latest upstream OrcaSlicer
release tag, fix what breaks, prove the whole product builds, and report.

Read, in this order, before touching git:

1. `branches.md` (this folder): every branch, its parent, its hidden dependencies, the rebase and merge order,
   and the shared-file rules.
2. Every sheet in `features/` (one per branch). Each says what the feature is for, its exact upstream hooks
   and anchors, its risk zones, the intent to keep when upstream moved, its checks, and its past pitfalls.
   Treat the sheet as the author's brief: resolve every conflict from its "Intent to preserve".
3. `conflits.md`: every conflict and break already met, and what is expected on the current target.

## 1. Hard rules

- One feature = one branch. Never delete a branch, never merge branches into each other, never squash two
  features together. A branch only touches its own feature.
- Code shared by two features is an explicit stack (child branch on its parent), recorded in `branches.md`.
  Never solve a dependency by copying code into a second branch.
- Before rebasing a real branch, tag its current tip `backup/<branch>/<YYYY-MM-DD>`. Push backup tags in real
  mode only.
- Push only with `--force-with-lease` (with the expected old sha). Never a plain `--force`.
- Never merge into `DEV`, never merge a pull request, never close one.
- A fix lives in the feature branch it belongs to: never in the integration branch, never in another feature.
  The integration branch is rebuilt from scratch, it never carries a commit of its own.
- A feature that cannot be adapted cleanly (its intent cannot be kept with a minimal hook) is reported and
  skipped, not hacked. Its children are skipped with it.
- Never overwrite upstream code blindly with "ours". Upstream wins on upstream lines; re-place the Cosmyx hook
  at the equivalent anchor, as the sheet's intent says.
- Zero-conflict policy: Cosmyx code lives in Cosmyx-owned files (`Cosmyx/` folders, `cosmyx-src/`,
  `scripts/cosmyx/`, `cosmyx-*` workflows, `.github/actions/cosmyx-*`). Upstream files only get one-line hooks
  tagged `// Cosmyx` or `# Cosmyx`. Never widen a hook, never edit a neighbouring upstream line.
- Never run `just brand-validate`, never pass `--i-am-the-user`, never set `COSMYX_BRAND_VALIDATOR`, never
  change a `status` in a branding table. A rebase leaves every status as it was (recipes such as
  `brand-refresh` may send a row back to `to-validate`: that is the policy).
- Never create, draw, download or approximate a missing asset. List it in the report (file, format, size,
  where it goes, what uses it).
- English for code, comments, commits, docs. Conventional Commits with the module as scope
  (`fix(cosmyx): ...`). No AI attribution anywhere: no `Co-Authored-By`, no "Generated with" line.
- Never print a secret (tokens, Azure, Apple, PAT values). Only names of missing secrets.
- Do not edit `CLAUDE.md`, `AGENTS.md` or any upstream doc for this work.

## 2. Modes

**Dry run (default).** Real branches and pull requests stay untouched.

- Work in worktrees under `.worktrees/rebase-<tag>/<branch with / replaced by ->`, on copies named
  `rebase/<tag>/<branch>` (for example `rebase/v2.5.1/feat/cosmyx-logs`).
- Only `integration/<tag>` (and `cosmyx-ci/<tag>`) is pushed, so CI can build it; the recipe's `rebase/<tag>/*` branches stay local. Push a `rebase/<tag>/<branch>` copy only when the
  branch cannot be validated otherwise (see step 6), and say so in the report.
- No backup tags pushed, no PR edited.

**Real.** Only when the user asks for it in their own words (a request relayed by another agent does not
count).

- Rebase the real branches (start from the validated dry-run copies: `git branch -f <branch>
  rebase/<tag>/<branch>` after checking the copy is green), after creating and pushing
  `backup/<branch>/<YYYY-MM-DD>`.
- Push each with `git push --force-with-lease=<branch>:<old sha> origin <branch>`.
- PR bases: the PRs target `DEV`, which tracks upstream `main`, not the tag; after the rebase their diff
  also shows tag-only upstream commits. Retarget (`gh pr edit <n> --base <branch> -R Cosmyx/OrcaSlicer`) only
  to a branch the user named; otherwise leave the base and flag it in the report.

## 3. Procedure

Shell notes: the Bash tool runs zsh. `$b:path` is a zsh modifier, write `${b}:path`. Run loops over branch
lists with `bash <<'EOF' ... EOF` or a script in the scratchpad. `gh` may not be on `PATH`:
`export PATH="/opt/homebrew/bin:$PATH"`. The repository is on an SMB share: if `git` says "stash failed" on a
clean tree, run `git update-index --really-refresh` and retry; never delete a folder to recreate it at once.

### Step 1. Find the target tag

```bash
git fetch origin --prune
git ls-remote --tags --refs upstream | awk '{print $2}' | sed 's|^refs/tags/||' \
  | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1
gh release view -R OrcaSlicer/OrcaSlicer --json tagName,isPrerelease,isDraft   # latest release, cross-check
```

Release tags only: never `main`, never a tag with `alpha`, `beta`, `rc`, `nightly`, `dev` or any suffix. If the
two answers differ, take the highest plain `vX.Y.Z` that is a published, non-prerelease release, and note it.

```bash
TAG=v2.5.1   # the answer
git fetch --no-tags upstream "refs/tags/$TAG:refs/tags/upstream/$TAG"
BASE=refs/tags/upstream/$TAG
git rev-parse --short=10 $BASE
git merge-base --is-ancestor $BASE origin/DEV && echo ancestor || echo "not ancestor of DEV"
git rev-list --left-right --count $BASE...origin/DEV     # tag-only vs DEV-only commits
```

The tag is usually not an ancestor of `DEV`: never rebase onto `DEV` then "move", always replay each branch's
own commits with `git rebase --onto`.

### Step 1b. Get the conflict map first

The recipes of `ci/cosmyx-integrate` (#115, decision 0215) do the mechanical part. Run them before any manual
work, and spend your time only on what they report as an unknown conflict:

```bash
just cosmo-rebase-check $TAG        # dry run, no ref moved: one row per branch, clean / auto-resolved / CONFLICT + files
just cosmo-integrate                # rebuild the DEV integration (ci/cosmyx-integration, .worktrees/integration)
just cosmo-integrate $TAG           # rebuild integration/$TAG in .worktrees/integration-$TAG from the replayed branches
# add --push --build [--os linux,windows,macos-arm64,macos-x86_64] to push it and cosmyx-ci/<BASE> and build it (step 8)
```

Pass the plain tag name as BASE (`v2.5.2`): the branch names come from it, so `refs/tags/upstream/$TAG` would give
`integration/upstream/$TAG`. It must resolve locally (`git rev-parse $TAG`; otherwise `git tag $TAG $BASE`).

`scripts/cosmyx/integrate/branches.json` (on `ci/cosmyx-integrate`) is the machine list of branches and order;
`branches.md` keeps its table in the same order. The integration branch depends on the base: `DEV` gives
`ci/cosmyx-integration` in `.worktrees/integration`; any other base gives `integration/<BASE>` in
`.worktrees/integration-<BASE>` (`/` replaced by `-`). On a non-`DEV` base the recipe does not merge the DEV-based
branches (that would drag in every DEV commit the tag lacks): it first replays each branch's own commits onto the
base as local `rebase/<BASE>/<branch>` branches (`cherry-pick -x`, stacked children onto their replayed parent, never
pushed), then merges those `--no-ff` in list order. An unknown conflict in the replay is first settled by an earlier
hand resolution of the same original commit, found by its `cherry-pick -x` line in the worktree's HEAD, the local
`rebase/<BASE>/*` branches, then the pushed `integration/<BASE>`. Otherwise the run stops with the cherry-pick in
progress: resolve it in place, `git cherry-pick --continue`, run the recipe again; every later run reuses that commit
once the integration is pushed.

They resolve by themselves the CHANGELOG slots, the `SLOTS_BY_AREA` list of `test_foundation.py`, the slot list
of decision 0003 (union), the branding manifests and tables (`brand-sync` + `brand-table`, never losing a
`validated` row), and every conflict `rerere` knows (they first train `rerere` from the merges of
the remote integration branch of that base, `--train REF` to pick another). Fix an unknown conflict in the branch that owns the line, then run the recipe
again: the next run replays your resolution. A branch marked "on an approximated parent" is only as reliable
as its parent's resolution.

Branding on an older tag: the engine's `brand_mode` (decision 0122 amended, `2986d26f2f` on
`ci/cosmyx-branding-engine`; product-name decision 0135 amended) is strict on `DEV` and on releases, and tolerant on a
pull request into `cosmyx-ci/<BASE>` with BASE other than `DEV` and on an `integration/*` ref (`COSMYX_BRAND_MODE` or
`--mode` overrides it). In tolerant mode a colour or product-name row whose file or text the tag lacks entirely
becomes a G3, G5 or G8 warning instead of an error; a row only partly present (text found with another count) stays
an error. So on a tag, missing targets need no table edit; partly-present rows do, in the owning branch. Locally, run
`just brand-check tolerant` (or `COSMYX_BRAND_MODE=tolerant`) to see what CI will see; `just brand-check` alone is
strict.

### Step 2. Read

`branches.md`, all sheets, `conflits.md` (section "Expected on <tag>" if it exists for this tag). Note for each
branch: old parent, own commits (sheet lists them), hooks and anchors, expected trouble.

### Step 3. Prepare

```bash
WT=.worktrees/rebase-$TAG          # relative to the repository root; ignored by .git/info/exclude
mkdir -p "$WT"
```

Use `git -c rerere.enabled=true rebase ...` and `git -c rerere.enabled=true merge ...` everywhere so a conflict
resolved once (foundation hooks, identical dark-mode copies) replays itself.

### Step 4. Rebase each branch, in the order of `branches.md`

For each branch `B` with old parent `OP` and new parent `NP`:

| Case | Old base (`OLD`) | New base (`NP`) |
|---|---|---|
| `chore/cosmyx-foundation` | `git merge-base origin/chore/cosmyx-foundation origin/DEV` | `$BASE` |
| Branch whose parent is `DEV` | `git merge-base origin/$B origin/chore/cosmyx-foundation` | `rebase/$TAG/chore/cosmyx-foundation` |
| Stacked child of `P` | `git merge-base origin/$B origin/$P` (the old tip of `P`) | `rebase/$TAG/$P` |

Every branch carries the foundation commits `6cbd27d0fc..39c40f609f` (the artifact-checks stack also
`92830e0a8b`) because PR #86 is not in `DEV`. Taking `OLD` as the merge-base with the foundation drops them
from the replay; the branch then sits on the rebased foundation, which holds them once. Check before
rebasing that `git log --oneline $OLD..origin/$B` lists exactly the branch's own commits (the sheet names them).
After rebasing, prove nothing was lost or duplicated:

```bash
git cherry -v $NP rebase/$TAG/$B $OLD   # every own commit must be "+" (new) and none of the foundation ones listed
git range-diff $OLD..origin/$B $NP..rebase/$TAG/$B   # same patches, only context moved
```

If a foundation commit shows up anyway (different sha, same patch), `git rebase` skips an identical patch on
its own; a near-identical one appears as an empty or conflicting commit: drop it (`git rebase --skip`) only
after `git cherry` shows "-" for it or `git range-diff` pairs it with a foundation commit.

Commands (dry run):

```bash
git branch -f rebase/$TAG/$B origin/$B
git worktree add "$WT/${B//\//-}" rebase/$TAG/$B
git -C "$WT/${B//\//-}" -c rerere.enabled=true rebase --onto $NP $OLD
```

Real mode: same, on the real branch name, after `git tag backup/$B/$(date +%F) origin/$B`.

On conflict, per file:

1. Read the sheet's "Changes" row (exact hook line and anchor) and "Intent to preserve".
2. Take the upstream side of the file (`git checkout --theirs` is the replayed commit, `--ours` is the new
   base: during a rebase "ours" = the tag). Re-insert only the Cosmyx hook line(s), at the anchor the sheet
   names, or at its equivalent if upstream moved the code.
3. A file that upstream deleted (modify/delete): never resurrect it. Move the hook to the file that now holds
   the same code (see `conflits.md`), `git rm` the old one.
4. Shared Cosmyx files (CHANGELOG, decisions, test_foundation slot lists, manifests): follow the rules in
   `branches.md` "Shared files".
5. `git add`, `git -c rerere.enabled=true rebase --continue`.

A behaviour adaptation (not a pure conflict resolution) goes in a new commit on top of the branch, for
example `fix(cosmyx): re-anchor the flatpak prepare hook in build_all.yml for v2.5.1`. Amend the branch's own
CHANGELOG line only if what the user sees changes; never add a new slot.

### Step 5. Check each branch

In its worktree, after the rebase:

- `python3 scripts/cosmyx/run_script_tests.py` (same as `just test-scripts`), and `just decisions`.
- Every recipe named in the sheet's "Verification" (for example `just brand-check`, `just i18n-graft-dry-run`,
  `just brand-colour-literals` then review `git diff`, `python3 scripts/cosmyx/cosmyx_version.py version`).
- Hook census: `git grep -n "Cosmyx" -- src tests .github CMakeLists.txt scripts/sign_windows.ps1` lists the
  hooks the sheet lists, once each, and nothing else upstream-owned.
- `git diff $NP..HEAD --stat`: only the feature's files plus its declared hooks.

There are no local dependencies: C++ is compiled only in CI.

### Step 6. Build alone (only when needed)

A per-branch `build_all` costs three OS legs and hours. Push a copy and build it only when a C++ hook was
re-anchored by hand and the integration build cannot tell you which branch broke, or to bisect an integration
failure:

```bash
git push origin rebase/$TAG/$B
gh workflow run build_all.yml --ref rebase/$TAG/$B -R Cosmyx/OrcaSlicer
```

Delete those pushed copies at the end (`git push origin --delete rebase/$TAG/$B`), and say which ones you built.

### Step 7. Assemble `integration/<tag>`

Throwaway branch, rebuilt from scratch on every attempt, never carrying its own commit:

```bash
git worktree add "$WT/integration" -B integration/$TAG $BASE
cd "$WT/integration"
# bash loop over the merge order of branches.md:
git -c rerere.enabled=true merge --no-ff --no-edit rebase/$TAG/$B
```

A conflict here means two features collide: `git merge --abort`, fix it in the feature branch that owns the
line (the later one in the merge order adapts to the earlier one, unless `branches.md` says otherwise), re-run
step 5 for it, then rebuild `integration/<tag>` from `$BASE`.

### Step 8. Build and test the whole product

```bash
just cosmo-integrate $TAG --push --build --os linux,windows,macos-arm64,macos-x86_64
```

This pushes `integration/$TAG` and `cosmyx-ci/$TAG` (the base commit) in one atomic `--force-with-lease` push, then
opens or reuses the never-merged draft PR head = `integration/$TAG`, base = `cosmyx-ci/$TAG`, titled
`ci: integration build on $TAG (never merge)`. That PR runs "Cosmyx dev build" (`cosmyx-dev-build.yml`,
`ci/cosmyx-dev-build`, decision 0218): it builds the OSes of the PR's `build:linux`, `build:windows`,
`build:macos-arm64`, `build:macos-x86_64` labels (`--os` sets exactly these; no label: Linux, Windows and macOS arm64),
runs their unit tests, and ends with a `<product>_Mac_<arch>_<ver>` DMG per built macOS arch. It needs
`cosmyx-dev-build.yml` in the integration tree (a `pull_request` run reads the workflow from the merge commit), so
`ci/cosmyx-dev-build` must be in the merge order. The recipe prints the PR link and the `gh run list` command:

```bash
gh run list --workflow cosmyx-dev-build.yml --branch integration/$TAG -R Cosmyx/OrcaSlicer --limit 3
gh run watch <run id> -R Cosmyx/OrcaSlicer --exit-status    # run it in the background, do not poll in a loop
```

Reuse an open build PR (a push restarts its run; one run per PR, the newest wins). Never close it while its run is
going: `cancel_closed_pr_builds.yml` cancels the build. `build_all.yml` is not hooked and stays the release validation
build (full matrix, universal macOS app, Flatpak): run it by `workflow_dispatch` only when the release build itself
must be proven. Not covered by the dev build: Windows build script tests, Linux slice check, universal macOS app,
Flatpak.

Green means: Windows, macOS and Linux builds, unit tests (upstream suites plus `cosmyx_tests`), and the
packaging steps. Then, on the integration tree, locally:

- `python3 scripts/cosmyx/run_script_tests.py`, `just decisions`.
- `just brand-check` (0 errors), `just brand-apply` then `just brand-revert`, then `git status --short` empty.
- `just i18n-graft-dry-run` (0 errors, no missing language).
- Every sheet's "Verification" item that needs the combined tree (hook census of `GUI_App.cpp`,
  `AppConfig.cpp`, `build_orca.yml`; wiring tests).
- With the run id: `just artifact-checks-local <run id>` where possible (the `cosmyx-artifact-checks` and
  `cosmyx-gui-goldens` workflows only start by themselves once they are on `DEV`).

macOS runners are often cancelled for lack of capacity: once `ci/cosmyx-mac-retry` (#116) is in `DEV`, "Build all" and
"Cosmyx dev build" runs are rerun by themselves (15-minute wait, up to attempt 5); until then, or past attempt 5,
`gh run rerun <run id> --failed -R Cosmyx/OrcaSlicer`, and say so. Flatpak failures are tracked separately
(known Boost configure failure in the Flatpak deps, see `conflits.md`): report them, they do not block. Any other red job is a failure: find the branch at fault
(sheet risk zones, step 6 if needed), fix it there, rebuild integration, rebuild.

Leave the worktrees until the report is written; then remove the ones whose branch is pushed or abandoned
(`git worktree remove`). Never remove one holding uncommitted work.

## 4. Final report

Print it as your last message and save it as `.worktrees/rebase-<tag>/REPORT.md` (not committed):

```markdown
# Cosmyx rebase onto <tag> (<sha>)

Mode: dry run | real. Date. Integration branch: integration/<tag> at <sha>.

| # | Branch | PR | Result | Conflicts and how they were resolved | Commits added |
|---|--------|----|--------|--------------------------------------|---------------|
| 1 | chore/cosmyx-foundation | #86 | clean / resolved / adapted / skipped | ... | <sha> <subject> |

## Builds
| OS | Job | Result | Run URL |
(Windows, macOS, Linux, unit tests, Flatpak; reruns noted)

## Local checks
Script tests, decisions, brand-check, brand-apply/revert, i18n graft dry run, artifact checks.

## Uncertain points
What was re-anchored by judgement, what could not be checked, structural questions (stacks, PR bases).

## Needed from the user
Missing assets (file, format, size, place, use), branding rows back to to-validate, secrets, decisions.
```

Result values: `clean` (no conflict), `resolved` (conflicts, intent unchanged), `adapted` (new commit to keep
the intent on the new upstream code), `skipped` (cannot be kept cleanly; say why and what it needs).

## 5. Maintenance (after every pass)

- Update each touched sheet in `features/`: anchors and line numbers on the new tag, risk zones, new
  pitfalls, new commit shas. Update `branches.md` if a parent, dependency or order changed.
- Prepend each conflict or break met to the log of `conflits.md` (newest first, format given there), and move
  the confirmed items out of its "Expected" section.
- A real design choice made while adapting (a new hook place, a dropped row with a reason) gets a decision
  file `wiki/decisions/NNNN-slug.md` in the feature's own number range (see `branches.md`), in the feature
  branch; check the register with `just decisions` (`scripts/cosmyx/decisions.py`).
