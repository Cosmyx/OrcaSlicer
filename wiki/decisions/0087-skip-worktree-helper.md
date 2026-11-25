# 0087. Build-time edits are hidden from git diff with skip-worktree

## Status

Accepted.

## Context

The CI edits tracked files in place before it builds: the translation graft
(decision 0080) and, from T11, the branding overlay. When the build has no
commit hash to stamp (push builds set `git_commit_hash` empty in
`build_orca.yml`), `src/slic3r/GitCommitHash.cmake` runs `git diff --quiet
HEAD` and appends `-dirty` to the version when it fails, so every such build
would be marked dirty. Untracked files never count.

## Decision

- `scripts/cosmyx/worktree_clean.py` is the one helper, shared by the
  translation graft and the branding:
  - `hide` sets the skip-worktree bit on every tracked file that differs from
    HEAD (`git diff --name-only -z HEAD` piped to `git update-index
    --skip-worktree -z --stdin`), then checks that `git diff --quiet HEAD`
    passes, and fails listing the files when it does not (a staged change
    cannot be hidden this way).
  - `show` lists the skip-worktree files.
  - `unhide [PATHSPEC...]` clears the bit and restores the committed content.
- `hide` is always the last step of `.github/actions/cosmyx-prepare`: every
  step that edits tracked files goes before it. The action exports the Python
  it uses as `COSMYX_PYTHON` (through `GITHUB_ENV`) for those steps.
- Locally, `just i18n-ungraft` runs `unhide localization/i18n` before it
  restores the catalogues, and `just worktree-hidden` lists what is hidden.

## Consequences

- CI builds keep a clean version string while building the edited files.
- A tree prepared by the action looks clean to git: `just worktree-hidden`
  shows what is really changed. Git treats a hidden file as unchanged, so a
  later checkout or pull may refuse or overwrite it; on a developer machine,
  unhide first. CI checkouts are throwaway, so this never matters there.
- Removing it: delete the hide step and the script; push builds are then
  marked `-dirty` again.
