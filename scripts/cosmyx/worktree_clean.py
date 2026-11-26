"""Keep a build-time edit of tracked files out of `git diff`.

The CI edits tracked files in place before it builds (the translation graft,
and later the branding overlay). OrcaSlicer marks a build "-dirty" when
`git diff --quiet HEAD` fails (src/slic3r/GitCommitHash.cmake), so those edits
would brand every CI build as dirty. This helper sets git's skip-worktree bit
on the edited files, so git reads them from the index and the tree looks clean,
while the edited content stays on disk for the build.

Commands (run from anywhere inside the repository, or pass --repo):

- `hide`: mark every tracked file that differs from HEAD as skip-worktree, then
  check that `git diff --quiet HEAD` passes; it fails, listing the files still
  showing, when it does not (for example a staged change). Untracked files are
  left alone: git never counts them as dirty.
- `show`: list the skip-worktree files.
- `unhide [PATHSPEC...]`: clear the bit and restore the committed content of
  those files. Without a pathspec it acts on every skip-worktree file. The
  pathspecs select the files with git's usual patterns; the files found are
  then restored by their exact names, so a name holding `[`, `*` or `?` never
  restores another file.

Pathspecs are relative to the repository root. Exit codes: 0 done, 1 the tree
is still dirty after `hide`, 2 git failed.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


class GitError(Exception):
    pass


def git(root: Path, *args: str, stdin: bytes | None = None, check: bool = True, literal: bool = False) -> subprocess.CompletedProcess:
    """Run git in `root` and return the completed process (stdout as bytes).
    With `literal`, every pathspec is a plain file name: `[`, `*` or `?` in a
    name never match other files."""
    env = None
    if literal:
        env = dict(os.environ, GIT_LITERAL_PATHSPECS="1")
    process = subprocess.run(
        ["git", "-C", str(root), *args],
        input=stdin,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and process.returncode != 0:
        message = process.stderr.decode("utf-8", "replace").strip()
        raise GitError(f"git {' '.join(args)} failed: {message}")
    return process


def toplevel(start: Path) -> Path:
    output = git(start, "rev-parse", "--show-toplevel").stdout.decode("utf-8", "surrogateescape").strip()
    return Path(output)


def split_z(data: bytes) -> list[bytes]:
    return [item for item in data.split(b"\0") if item]


def changed_files(root: Path) -> list[bytes]:
    """Tracked files whose working tree or index content differs from HEAD."""
    return split_z(git(root, "diff", "--name-only", "--no-renames", "-z", "HEAD").stdout)


def hidden_files(root: Path, pathspecs: list[str] | None = None) -> list[bytes]:
    """Files with the skip-worktree bit (tag `S` in `git ls-files -v`)."""
    args = ["ls-files", "-v", "-z"]
    if pathspecs:
        args += ["--", *pathspecs]
    entries = split_z(git(root, *args).stdout)
    return [entry[2:] for entry in entries if entry.startswith(b"S ")]


def display(path: bytes) -> str:
    return path.decode("utf-8", "replace")


def hide(root: Path) -> int:
    files = changed_files(root)
    if files:
        git(root, "update-index", "--skip-worktree", "-z", "--stdin", stdin=b"\0".join(files) + b"\0")
    if git(root, "diff", "--quiet", "HEAD", check=False).returncode != 0:
        print("error: the tree still differs from HEAD after hiding the edited files:", file=sys.stderr)
        for path in changed_files(root):
            print(f"  {display(path)}", file=sys.stderr)
        return 1
    print(f"Hid {len(files)} edited file(s) from git diff.")
    return 0


def show(root: Path) -> int:
    for path in hidden_files(root):
        print(display(path))
    return 0


def unhide(root: Path, pathspecs: list[str]) -> int:
    files = hidden_files(root, pathspecs)
    if files:
        listing = b"\0".join(files) + b"\0"
        git(root, "update-index", "--no-skip-worktree", "-z", "--stdin", stdin=listing)
        # The listing holds exact file names, not patterns.
        git(root, "checkout", "--pathspec-from-file=-", "--pathspec-file-nul", "--", stdin=listing, literal=True)
    print(f"Restored {len(files)} file(s).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hide build-time edits of tracked files from git diff.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="a folder inside the repository (default: here)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("hide", help="mark the edited tracked files skip-worktree and check the tree is clean")
    sub.add_parser("show", help="list the skip-worktree files")
    un = sub.add_parser("unhide", help="clear skip-worktree and restore the committed content")
    un.add_argument("pathspecs", nargs="*", help="limit to these pathspecs, relative to the repository root")
    args = parser.parse_args(argv)

    try:
        root = toplevel(args.repo)
        if args.command == "hide":
            return hide(root)
        if args.command == "show":
            return show(root)
        return unhide(root, args.pathspecs)
    except (GitError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
