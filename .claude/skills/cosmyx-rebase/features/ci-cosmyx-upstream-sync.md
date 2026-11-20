# ci/cosmyx-upstream-sync (PR #87)

## Purpose

Keeps the fork following upstream automatically and proves the "zero conflict with upstream" rule continuously. The `cosmyx-upstream-sync` workflow runs every six hours (cron `23 */6 * * *`) and on manual dispatch, in this order:

1. mirror: force-push `OrcaSlicer/OrcaSlicer` `main` to `Orca-Upstream`.
2. mixed: rebuild `MIXED` as `DEV` merged with `Orca-Upstream` (no working tree, `git merge-tree --write-tree`), a two-parent commit whose message ends with the trailer `Cosmyx-Mixed: base=<sha> upstream=<sha>`; skipped when the trailer shows nothing changed. A conflict fails the run (exit 2) and lists the files as annotations and in the job summary.
3. dispatch: start `build_all.yml` on `MIXED` only when it moved.
4. workflow-policy: every upstream workflow with a `schedule:` trigger must be in `allow_scheduled` or `disable` of `.github/cosmyx/workflow-policy.json`, otherwise the run fails; the listed bots (`stale`, `approve_pr_checks`, `assign`, `auto-close-duplicates`) are disabled through the GitHub API (repository setting, never editing their files). Files matching `cosmyx-*.yml` are exempt (decision 0105).

It replaces the old `sync_orca_upstream.yml`, lost when the default branch changed to `DEV`. Uses secret `UPSTREAM_SYNC_TOKEN` (fine-grained PAT, Contents and Workflows read/write), since `GITHUB_TOKEN` cannot push commits touching `.github/workflows/`.

## Parent and dependencies

Parent: `DEV`, and it carries the foundation commits (`chore/cosmyx-foundation`, #86); its own commits are `1df879836d`, `cc6852dc09`, `2f6a197b69`, `0ca6bd3401`, `930b83ccbb`, `316de4e02f`, `684376d5bb`, `4601573750`. It calls no upstream code. It depends on upstream only through (a) the set of workflow files carrying a `schedule:` trigger, (b) the name `build_all.yml`, and (c) git history of the `OrcaSlicer/OrcaSlicer` `main` branch. Branch names `DEV`, `Orca-Upstream`, `MIXED` are hard-wired.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `.github/workflows/cosmyx-upstream-sync.yml` | CI (Cosmyx-owned) | Jobs mirror, mixed, dispatch, workflow-policy; concurrency group `cosmyx-upstream-sync`, never cancels a running sync; `dry_run` input. |
| `.github/cosmyx/workflow-policy.json` | data | Lists `disable`, `allow_scheduled`, `must_stay_enabled`, `cosmyx_owned_glob`. |
| `scripts/cosmyx/upstream_sync.py` | Cosmyx-owned script | stdlib only; subcommands `mirror`, `mixed`, `workflow-policy`; helpers `remote_sha`, `merge_trees`, `is_scheduled`, `check_policy`, `apply_policy`, `redact`. |
| `scripts/cosmyx/just/sync.just` | Cosmyx-owned | Recipes `sync-mixed-dry-run`, `workflow-policy`, `workflow-policy-apply`, `sync-dispatch`. |
| `scripts/cosmyx/tests/test_upstream_sync.py`, `test_breaker_upstream_sync_ls_remote.py`, `test_breaker_workflow_policy_yaml.py` | test | Temporary bare repositories and a fake `gh`. |
| `wiki/cosmyx/upstream-sync.md`, `wiki/decisions/0100-0105` | docs | Design and decisions. |
| `CHANGELOG.md` | docs | One line under the T10 slot. |
| `tests/CMakeLists.txt` | upstream hook | Foundation hook `add_subdirectory(cosmyx) # Cosmyx` (inherited from the foundation; this branch adds no new upstream line). |
| Foundation files | see `chore-cosmyx-foundation.md` | Carried unchanged. |

No upstream file is edited by this branch's own commits.

## Rebase risk zones

- Upstream scheduled workflows. DEV has `approve_pr_checks.yml assign.yml auto-close-duplicates.yml build_all.yml doxygen-docs.yml ofl-ota-cronjob.yml parity_nightly.yml shellcheck.yml stale.yml wait-for-response-label.yml`. The tag v2.5.1 has the same set minus `stale.yml` and `wait-for-response-label.yml` (they do not exist in the tag). The policy lists a superset, which is tolerated (`apply` leaves unregistered workflows alone). Test `test_repository_policy_covers_every_scheduled_workflow` reads the real `.github/workflows/` and must pass against the tag's directory; any new scheduled workflow upstream adds in the target release must be added to the policy file.
- `build_all.yml` differs hugely between DEV and the tag (316 lines changed). The sync only dispatches it by name; it must still exist and accept `workflow_dispatch` (check `on:` of the target's `build_all.yml`).
- Churn: none of the hooked upstream files apply; `.github/workflows/*` churn on DEV is high, which is why the policy exists.

## Intent to preserve

- `MIXED` is the guard: DEV plus upstream main must merge with zero conflicts, rebuilt every 6 hours. A conflict is a bug fixed on DEV by shrinking the hook, never by editing the sync.
- `Orca-Upstream` is an exact mirror (follows upstream history rewrites); the `ls-remote` match must be exact on the ref.
- The policy never lets an unreviewed upstream scheduled workflow run on the fork, and never disables `build_all.yml` or this sync.
- On a release-tag rebase the sync itself needs no hook, since all files are Cosmyx-owned; it is rebased wholesale. If the tag's workflow set differs, only edit the JSON lists. Do not point the sync at the release tag: it must track `main`.

## Verification

- `just test-scripts`: `MirrorTests`, `MixedTests` (clean merge two parents and trailer, unchanged inputs push nothing, conflict exit code 2, dry run), `TrailerAndRedactTests`, `WorkflowPolicyTests` (including `test_repository_policy_covers_every_scheduled_workflow` and `test_repository_policy_keeps_build_all_enabled`), `WorkflowFileTests` (`test_is_ascii_and_lf` reads the git index blob), and the two `test_breaker_*` modules.
- `just workflow-policy` against the rebased tree; `just sync-mixed-dry-run`.
- After merge: `just sync-dispatch` (dry run), then `just sync-dispatch false`; the workflow only runs from the default branch.

## Known pitfalls

- 4601573750: on the Windows runner the checkout converts to CRLF (`core.autocrlf`), so the LF test on the workflow file failed. The test reads the committed blob with `git cat-file`.
- 684376d5bb: `git ls-remote` matches ref patterns by tail, so a branch `0/refs/heads/Orca-Upstream` was taken for `Orca-Upstream` and the mirror silently stopped; also `is_scheduled` missed schedules behind YAML aliases or multi-line flow mappings (tests 930b83ccbb, 316de4e02f). The scan now fails closed.
- 0ca6bd3401: Cosmyx's own scheduled workflows (GUI goldens) must not need policy entries, or every such PR would edit the same lists: `cosmyx_owned_glob`.
- Scheduled workflows run only from the default branch and auto-disable after 60 days without activity (decision 0103).

## Shared files with other branches

`CHANGELOG.md`, `justfile` (the `import? '.../sync.just'` line already exists in the foundation justfile), `scripts/cosmyx/run_script_tests.py`, `scripts/cosmyx/decisions.py`, `scripts/cosmyx/tests/test_foundation.py` (this branch holds a 190-line variant), `.github/workflows/cosmyx-checks.yml`, `wiki/decisions/0001-0004`, `wiki/decisions/README.md`, `tests/CMakeLists.txt`, and `.github/cosmyx/workflow-policy.json` (any future branch that adds a scheduled non-`cosmyx-*` workflow must edit it). The foundation commits are common to every branch, so after rebasing the foundation, rebase this branch onto it and drop the duplicated foundation commits.
