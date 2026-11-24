"""Pre-chew the integration and rebase work of the Cosmyx branch stack.

    python scripts/cosmyx/integrate/cli.py integrate [BASE] [--push [--build]]
    python scripts/cosmyx/integrate/cli.py rebase-check TAG

`integrate` rebuilds the throwaway branch `ci/cosmyx-integration` in the
worktree `.worktrees/integration` (created, or reused when clean) from BASE
(default `origin/DEV`), merging `origin/<branch>` with `--no-ff` in the order
of `branches.json`. Known conflict kinds are resolved inside the merge commit
(see resolve.py; `rerere` is on for the run). Any other conflict aborts that
merge, prints the branch, the files and a summary of their hunks, and exits 1.
Nothing is pushed unless `--push` (force-with-lease on the old remote tip);
`--build` then starts build_all on the branch.

`rebase-check` is a dry run: in a temporary worktree, it replays each branch's
own commits onto `refs/tags/upstream/TAG` (stacked children onto their
replayed parent) with the same auto-resolutions, and prints a table. No
branch is created, moved or pushed; the temporary worktree is always removed.

Exit codes: 0 done, 1 unknown conflict (integrate) or conflicts found
(rebase-check), 2 usage or setup error.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

if __package__ in (None, ""):
    # Run as a script: make the package importable from scripts/cosmyx.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from integrate import resolve  # noqa: E402

DATA_FILE = Path(__file__).resolve().parent / "branches.json"
UPSTREAM_URL = "https://github.com/OrcaSlicer/OrcaSlicer.git"
INTEGRATION_BRANCH = "ci/cosmyx-integration"
INTEGRATION_WORKTREE = Path(".worktrees") / "integration"
# Settings for every merge or cherry-pick of a run: rerere replays recorded
# resolutions. The default conflict style is forced so that rerere finds the
# resolutions recorded by hand merges (a diff3 hunk has another conflict id);
# the resolvers get the diff3 form of a file by `checkout --conflict=diff3`.
RUN_CONFIG = ["-c", "rerere.enabled=true", "-c", "rerere.autoupdate=false", "-c", "merge.conflictStyle=merge",
              "-c", "core.editor=true"]


class SetupError(Exception):
    """A usage or repository state problem: nothing was changed."""


class Git:
    def __init__(self, cwd: Path) -> None:
        self.cwd = Path(cwd)

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        env = dict(os.environ, LC_ALL="C", LANGUAGE="C", GIT_TERMINAL_PROMPT="0")
        completed = subprocess.run(["git", *RUN_CONFIG, *args], cwd=str(self.cwd), capture_output=True, text=True,
                                   encoding="utf-8", errors="replace", env=env, check=False)
        if check and completed.returncode != 0:
            raise SetupError(f"git {' '.join(args)} failed in {self.cwd}:\n{completed.stderr.strip()}")
        return completed

    def out(self, *args: str) -> str:
        return self.run(*args).stdout.strip()

    def sha(self, rev: str) -> str | None:
        completed = self.run("rev-parse", "-q", "--verify", f"{rev}^{{commit}}", check=False)
        return completed.stdout.strip() or None

    def blob(self, rev: str, path: str) -> str | None:
        completed = self.run("show", f"{rev}:{path}", check=False)
        return completed.stdout if completed.returncode == 0 else None


# Branch list


@dataclass
class Entry:
    name: str
    parent: str
    pr: int | None = None
    integration_only: bool = False


def load_branches(path: Path = DATA_FILE) -> tuple[dict, list[Entry]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = [Entry(row["name"], row["parent"], row.get("pr"), bool(row.get("integration_only")))
               for row in data["branches"]]
    check_branches(data, entries)
    return data, entries


def check_branches(data: dict, entries: list[Entry]) -> None:
    seen: set[str] = set()
    for entry in entries:
        if entry.name in seen:
            raise SetupError(f"{entry.name} is listed twice")
        if entry.parent != data["base"] and entry.parent not in seen:
            raise SetupError(f"{entry.name}: parent {entry.parent} must be {data['base']} or an earlier row")
        seen.add(entry.name)
    if entries and entries[0].name != data["foundation"]:
        raise SetupError(f"the first row must be the foundation {data['foundation']}")


# Conflict resolution


@dataclass
class Outcome:
    kinds: list[str] = field(default_factory=list)
    unknown: list[tuple[str, list[str]]] = field(default_factory=list)


BrandHook = Callable[[Path], None]


def run_branding_engine(worktree: Path) -> None:
    """Default branding hook: the worktree's own `brand-sync` and `brand-table`."""
    cli = worktree / "scripts" / "cosmyx" / "branding" / "cli.py"
    if not cli.is_file():
        raise resolve.Unresolvable("branding engine missing in the tree")
    for command in ("sync", "render"):
        completed = subprocess.run([sys.executable, str(cli), command], cwd=str(worktree), capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", check=False)
        if completed.returncode != 0:
            raise resolve.Unresolvable(f"branding {command} failed: {completed.stdout}{completed.stderr}".strip())


def unmerged(git: Git) -> dict[str, set[int]]:
    stages: dict[str, set[int]] = {}
    for record in git.out("ls-files", "-u", "-z").split("\0"):
        if not record:
            continue
        meta, path = record.split("\t", 1)
        stages.setdefault(path, set()).add(int(meta.split()[2]))
    return stages


def read(worktree: Path, path: str) -> str:
    return (worktree / path).read_bytes().decode("utf-8")


def write(worktree: Path, path: str, text: str) -> None:
    (worktree / path).write_bytes(text.encode("utf-8"))


def manifests_at(git: Git, rev: str) -> dict[str, str]:
    prefix = resolve.BRAND_PREFIXES[0]
    names = git.run("ls-tree", "--name-only", rev, prefix, check=False).stdout.split()
    return {name: git.blob(rev, name) or "{}" for name in names if name.endswith(".json")}


def manifests_in(worktree: Path) -> dict[str, str]:
    folder = worktree / resolve.BRAND_PREFIXES[0]
    return {path.name: path.read_bytes().decode("utf-8") for path in sorted(folder.glob("*.json"))}


def resolve_conflicts(git: Git, theirs_rev: str, brand_hook: BrandHook) -> Outcome:
    """Resolve the conflicts of the merge or cherry-pick in progress in git.cwd.

    Known kinds are resolved and staged. Unknown ones are listed in the outcome
    and left as they are; the caller aborts or overrides them.
    """
    worktree = git.cwd
    outcome = Outcome()
    stages = unmerged(git)
    if not stages:
        return outcome

    def note(kind: str) -> None:
        if kind not in outcome.kinds:
            outcome.kinds.append(kind)

    def unknown(path: str, why: list[str]) -> None:
        outcome.unknown.append((path, why))

    paths = sorted(stages, key=lambda path: (resolve.kind_of(path) != "changelog", path))
    brand_paths = []
    for path in paths:
        both = {2, 3} <= stages[path]
        if not both:
            unknown(path, [f"modify/delete or add conflict (stages {sorted(stages[path])})"])
            continue
        kind = resolve.kind_of(path)
        if kind == "branding":
            brand_paths.append(path)
            continue
        text = read(worktree, path)
        if not resolve.has_conflict_markers(text):
            # rerere already replayed a recorded resolution.
            git.run("add", "--", path)
            note("rerere")
            continue
        if kind is not None:
            # Rewrite the file from the index stages with the base of each hunk.
            git.run("checkout", "--conflict=diff3", "--", path)
            text = read(worktree, path)
        try:
            if kind == "changelog":
                text = resolve.resolve_changelog(text)
            elif kind == "slot-list":
                order = resolve.marker_order(read(worktree, resolve.CHANGELOG))
                text = resolve.resolve_slot_list(text, order, resolve.style_of(path))
            else:
                raise resolve.Unresolvable("not a known conflict kind")
        except resolve.Unresolvable as error:
            unknown(path, [str(error), *resolve.summarize(text)])
            continue
        write(worktree, path, text)
        git.run("add", "--", path)
        note(f"union:{path.rsplit('/', 1)[-1]}")
    if brand_paths and not outcome.unknown:
        try:
            resolve_branding(git, theirs_rev, brand_paths, brand_hook)
            note("brand-sync")
        except resolve.Unresolvable as error:
            for path in brand_paths:
                unknown(path, [str(error)])
    elif brand_paths:
        for path in brand_paths:
            unknown(path, ["branding table left for after the other conflicts"])
    return outcome


def resolve_branding(git: Git, theirs_rev: str, paths: list[str], brand_hook: BrandHook) -> None:
    """Take one side of every conflicted manifest or table, then regenerate.

    Ours is tried first, then theirs; a side is kept only when no row that is
    `validated` on either side lost that status.
    """
    before = resolve.validated_paths(manifests_at(git, "HEAD")) | resolve.validated_paths(
        manifests_at(git, theirs_rev))
    lost: set[str] = set()
    for side in ("--ours", "--theirs"):
        git.run("checkout", side, "--", *paths)
        brand_hook(git.cwd)
        after = resolve.validated_paths(manifests_in(git.cwd))
        lost = before - after
        if not lost:
            git.run("add", "--", *paths)
            git.run("add", "-A", "--", resolve.BRAND_PREFIXES[0].rstrip("/"), resolve.BRAND_PREFIXES[1].rstrip("/"))
            return
    raise resolve.Unresolvable(f"{len(lost)} validated rows lost on either side, e.g. {sorted(lost)[:3]}")


def report_unknown(label: str, outcome: Outcome, out) -> None:
    print(f"UNKNOWN CONFLICT in {label}:", file=out)
    for path, why in outcome.unknown:
        print(f"  {path}", file=out)
        for line in why:
            print(f"    {line}", file=out)


def table(rows: list[tuple[str, ...]], header: tuple[str, ...], out) -> None:
    widths = [max(len(str(row[i])) for row in [header, *rows]) for i in range(len(header))]
    line = lambda row: "| " + " | ".join(str(cell).ljust(width) for cell, width in zip(row, widths)) + " |"  # noqa: E731
    print(line(header), file=out)
    print("|" + "|".join("-" * (width + 2) for width in widths) + "|", file=out)
    for row in rows:
        print(line(row), file=out)


def train_rerere(wt: Git, ref: str, base: str, out) -> int:
    """Teach rerere the conflict resolutions recorded in the merges of `ref`.

    Same idea as git's contrib rerere-train: redo each conflicting merge of
    `ref` that `base` does not have, then show rerere the committed result.
    Leaves the worktree detached; the caller checks out what it needs.
    """
    learned = 0
    for merge in wt.out("rev-list", "--merges", "--reverse", ref, f"^{base}").split():
        parents = wt.out("rev-list", "--parents", "-n", "1", merge).split()[1:]
        if len(parents) != 2:
            continue
        if wt.run("merge-tree", "--write-tree", "--no-messages", *parents, check=False).returncode == 0:
            continue
        wt.run("checkout", "-q", "-f", "--detach", parents[0])
        wt.run("merge", "--no-ff", "--no-commit", parents[1], check=False)
        if wt.sha("MERGE_HEAD"):
            wt.run("checkout", merge, "--", ".")
            wt.run("rerere")
            learned += 1
        wt.run("reset", "-q", "--hard")
    print(f"rerere trained on {learned} conflicting merges of {ref}", file=out)
    return learned


# integrate


def main_root(git: Git) -> Path:
    """The main checkout (where .worktrees lives), from any of its worktrees."""
    common = Path(git.out("rev-parse", "--path-format=absolute", "--git-common-dir"))
    return common.parent


def prepare_worktree(git: Git, path: Path, branch: str, base: str) -> Git:
    if path.exists():
        wt = Git(path)
        top = wt.run("rev-parse", "--show-toplevel", check=False).stdout.strip()
        if not top or Path(top).resolve() != path.resolve():
            raise SetupError(f"{path} exists and is not a worktree of this repository")
        if wt.out("status", "--porcelain") or wt.sha("MERGE_HEAD") or wt.sha("CHERRY_PICK_HEAD"):
            raise SetupError(f"{path} is not clean: commit, stash or clean it first")
        wt.run("checkout", "-q", "-B", branch, base)
        return wt
    path.parent.mkdir(parents=True, exist_ok=True)
    git.run("worktree", "add", "-q", "-B", branch, str(path), base)
    return Git(path)


def integrate(args, out=sys.stdout, brand_hook: BrandHook = run_branding_engine, gh: Callable | None = None) -> int:
    git = Git(Path(args.repo_root) if args.repo_root else Path.cwd())
    data, entries = load_branches(Path(args.data) if args.data else DATA_FILE)
    remote = data["remote"]
    entries = [entry for entry in entries if entry.name not in set(args.skip or [])]
    if args.build and not args.push:
        raise SetupError("--build needs --push")
    if not args.no_fetch:
        git.run("fetch", "-q", "--prune", remote)
    base = args.base or f"{remote}/{data['base']}"
    base_sha = git.sha(base)
    if not base_sha:
        raise SetupError(f"base {base} not found")
    tips = {}
    for entry in entries:
        tips[entry.name] = git.sha(f"refs/remotes/{remote}/{entry.name}")
        if not tips[entry.name]:
            raise SetupError(f"{remote}/{entry.name} not found (fetch it, or --skip it)")
    old_tip = git.sha(f"refs/remotes/{remote}/{args.branch}")
    wt = prepare_worktree(git, main_root(git) / (args.worktree or INTEGRATION_WORKTREE), args.branch, base_sha)
    train = args.train or (f"refs/remotes/{remote}/{args.branch}" if not args.no_train else None)
    if train and git.sha(train):
        train_rerere(wt, train, base_sha, out)
        wt.run("checkout", "-q", "-f", "-B", args.branch, base_sha)
    print(f"{args.branch} reset to {base} ({base_sha[:10]}) in {wt.cwd}", file=out)
    rows: list[tuple[str, str, str]] = []
    for entry in entries:
        result = wt.run("merge", "--no-ff", "--no-commit", f"{remote}/{entry.name}", check=False)
        if not wt.sha("MERGE_HEAD"):
            if result.returncode != 0:
                raise SetupError(f"merge of {entry.name} failed:\n{result.stdout}{result.stderr}")
            rows.append((entry.name, tips[entry.name][:10], "already in"))
            continue
        outcome = resolve_conflicts(wt, "MERGE_HEAD", brand_hook)
        if outcome.unknown:
            report_unknown(f"{remote}/{entry.name} ({tips[entry.name][:10]})", outcome, out)
            wt.run("merge", "--abort")
            rows.append((entry.name, tips[entry.name][:10], "CONFLICT (merge aborted)"))
            table(rows, ("Branch", "Tip", "Result"), out)
            print(f"Stopped: {args.branch} holds the merges above; nothing pushed.", file=out)
            return 1
        wt.run("commit", "-q", "--no-verify", "--no-edit")
        rows.append((entry.name, tips[entry.name][:10],
                     "auto-resolved: " + ", ".join(outcome.kinds) if outcome.kinds else "clean"))
    tip = wt.out("rev-parse", "HEAD")
    table(rows, ("Branch", "Tip", "Result"), out)
    print(f"{args.branch} = {tip[:10]} (remote {old_tip[:10] if old_tip else 'absent'})", file=out)
    if not args.push:
        print("Not pushed (use --push).", file=out)
        return 0
    lease = f"--force-with-lease={args.branch}:{old_tip or ''}"
    wt.run("push", lease, remote, f"{args.branch}:refs/heads/{args.branch}")
    print(f"Pushed {args.branch} {tip[:10]}.", file=out)
    if args.build:
        command = ["workflow", "run", "build_all.yml", "--ref", args.branch]
        if args.repo:
            command += ["--repo", args.repo]
        completed = (gh or run_gh)(command)
        if completed.returncode != 0:
            print(f"gh {' '.join(command)} failed: {completed.stderr}", file=out)
            return 2
        print("build_all started.", file=out)
    return 0


def run_gh(args: list[str]) -> subprocess.CompletedProcess:
    executable = shutil.which("gh")
    if not executable:
        raise SetupError("gh is not installed")
    return subprocess.run([executable, *args], capture_output=True, text=True, encoding="utf-8", check=False)


# rebase-check


def upstream_tag(git: Git, tag: str, url: str, fetch: bool) -> str:
    ref = f"refs/tags/upstream/{tag}"
    sha = git.sha(ref)
    if not sha and fetch:
        git.run("fetch", "-q", "--no-tags", url, f"refs/tags/{tag}:{ref}")
        sha = git.sha(ref)
    if not sha:
        raise SetupError(f"{ref} not found")
    return sha


def take_theirs(git: Git, paths: list[str]) -> None:
    """Dry-run fallback for an unknown conflict: keep the replayed commit's side."""
    stages = unmerged(git)
    for path in paths:
        if 3 in stages.get(path, set()):
            git.run("checkout", "--theirs", "--", path)
            git.run("add", "--", path)
        else:
            git.run("rm", "-q", "--cached", "--ignore-unmatch", "--", path)
            target = git.cwd / path
            if target.exists():
                target.unlink()


def replay(wt: Git, commits: list[str], brand_hook: BrandHook) -> tuple[list[str], list[str]]:
    """Cherry-pick commits onto HEAD; return (auto-resolution kinds, conflicting files)."""
    kinds: list[str] = []
    conflicts: list[str] = []
    for commit in commits:
        result = wt.run("cherry-pick", "--allow-empty", "--empty=drop", commit, check=False)
        if result.returncode == 0:
            continue
        if not wt.sha("CHERRY_PICK_HEAD"):
            raise SetupError(f"cherry-pick {commit[:10]} failed:\n{result.stderr}")
        outcome = resolve_conflicts(wt, "CHERRY_PICK_HEAD", brand_hook)
        kinds.extend(kind for kind in outcome.kinds if kind not in kinds)
        if outcome.unknown:
            paths = [path for path, _ in outcome.unknown]
            conflicts.extend(f"{path} ({commit[:10]})" for path in paths)
            take_theirs(wt, paths)
        if wt.run("diff", "--cached", "--quiet", check=False).returncode == 0:
            wt.run("cherry-pick", "--skip")
        else:
            wt.run("commit", "-q", "--no-verify", "--no-edit", "--allow-empty")
    return kinds, conflicts


def rebase_check(args, out=sys.stdout, brand_hook: BrandHook = run_branding_engine) -> int:
    git = Git(Path(args.repo_root) if args.repo_root else Path.cwd())
    data, entries = load_branches(Path(args.data) if args.data else DATA_FILE)
    remote, foundation = data["remote"], data["foundation"]
    entries = [entry for entry in entries if not entry.integration_only and entry.name not in set(args.skip or [])]
    if not args.no_fetch:
        git.run("fetch", "-q", "--prune", remote)
    onto = upstream_tag(git, args.tag, args.upstream_url, not args.no_fetch)
    dev = git.sha(f"refs/remotes/{remote}/{data['base']}")
    if not dev:
        raise SetupError(f"{remote}/{data['base']} not found")
    rows: list[tuple[str, str, str, str]] = []
    replayed: dict[str, str] = {}
    approximated: set[str] = set()
    temp = Path(tempfile.mkdtemp(prefix="cosmyx-rebase-check-"))
    wt_path = temp / "wt"
    try:
        git.run("worktree", "add", "-q", "--detach", str(wt_path), onto)
        wt = Git(wt_path)
        if args.train:
            train_rerere(wt, args.train, onto, out)
        for entry in entries:
            tip = git.sha(f"refs/remotes/{remote}/{entry.name}")
            if not tip:
                rows.append((entry.name, "-", "MISSING", ""))
                continue
            if entry.name == foundation:
                old_base, new_base, parent = git.out("merge-base", tip, dev), onto, None
            else:
                parent = foundation if entry.parent == data["base"] else entry.parent
                parent_tip = git.sha(f"refs/remotes/{remote}/{parent}")
                new_base = replayed.get(parent)
                if not parent_tip or not new_base:
                    rows.append((entry.name, tip[:10], f"SKIPPED (parent {parent} not replayed)", ""))
                    continue
                old_base = git.out("merge-base", tip, parent_tip)
            commits = git.out("rev-list", "--reverse", "--no-merges", f"{old_base}..{tip}").split()
            wt.run("checkout", "-q", "-f", "--detach", new_base)
            kinds, conflicts = replay(wt, commits, brand_hook)
            replayed[entry.name] = wt.out("rev-parse", "HEAD")
            if conflicts:
                approximated.add(entry.name)
                result = "CONFLICT"
            elif kinds:
                result = "auto-resolved: " + ", ".join(kinds)
            else:
                result = "clean"
            if parent in approximated:
                approximated.add(entry.name)
                result += " (on an approximated parent)"
            rows.append((entry.name, f"{len(commits)} commits", result, "; ".join(conflicts)))
    finally:
        if wt_path.exists():
            git.run("worktree", "remove", "--force", str(wt_path), check=False)
        shutil.rmtree(temp, ignore_errors=True)
        git.run("worktree", "prune", check=False)
    print(f"Rebase check onto upstream/{args.tag} ({onto[:10]}); nothing changed.", file=out)
    table(rows, ("Branch", "Replayed", "Result", "Conflicting files"), out)
    if approximated:
        print("CONFLICT: unknown conflicts were overridden with the branch's side to keep going; "
              "branches stacked on them are approximate.", file=out)
    return 1 if any(row[2].startswith(("CONFLICT", "SKIPPED", "MISSING")) for row in rows) else 0


# command line


def parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data", help="branch list (default: branches.json next to this script)")
    common.add_argument("--repo-root", help="any checkout of the repository (default: current directory)")
    common.add_argument("--skip", action="append", metavar="BRANCH", help="leave a branch out (repeatable)")
    common.add_argument("--no-fetch", action="store_true", help="use the remote-tracking refs as they are")
    common.add_argument("--train", metavar="REF", help="teach rerere the resolutions of REF's merges first")
    top = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = top.add_subparsers(dest="command", required=True)
    one = sub.add_parser("integrate", parents=[common], help="rebuild the integration branch")
    one.add_argument("base", nargs="?", help="start point (default: <remote>/DEV)")
    one.add_argument("--branch", default=INTEGRATION_BRANCH)
    one.add_argument("--worktree", help=f"worktree path under the main checkout (default: {INTEGRATION_WORKTREE})")
    one.add_argument("--no-train", action="store_true",
                     help="do not teach rerere from the current remote integration branch")
    one.add_argument("--push", action="store_true", help="push with --force-with-lease on the old remote tip")
    one.add_argument("--build", action="store_true", help="after --push, start build_all on the branch")
    one.add_argument("--repo", default=os.environ.get("COSMYX_REPO"), help="GitHub repository for --build")
    two = sub.add_parser("rebase-check", parents=[common], help="dry-run rebase onto an upstream tag")
    two.add_argument("tag")
    two.add_argument("--upstream-url", default=UPSTREAM_URL)
    return top


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "integrate":
            return integrate(args)
        return rebase_check(args)
    except SetupError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
