"""Pre-chew the integration and rebase work of the Cosmyx branch stack.

    python scripts/cosmyx/integrate/cli.py integrate [BASE] [--push [--build [--os LIST]]]
    python scripts/cosmyx/integrate/cli.py rebase-check TAG

`integrate` rebuilds a throwaway integration branch in its own worktree
(created, or reused when clean) from BASE (default `origin/DEV`): for the
list's base (DEV) `ci/cosmyx-integration` in `.worktrees/integration`, for any
other BASE `integration/<BASE>` in `.worktrees/integration-<BASE>`, so that
the integrations of different bases coexist. For the list's base it merges
`origin/<branch>` with `--no-ff` in the order of `branches.json`. For any other
base the branches would drag in every DEV commit BASE lacks, so each branch's
own commits are first replayed onto BASE (stacked children onto their replayed
parent) as the local branch `rebase/<BASE>/<branch>`, and those are merged.
A branch already checked out in another worktree is moved there, only when
that worktree is clean. Known conflict kinds are resolved inside the merge or
cherry-pick commit (see resolve.py; `rerere` is on for the run). Any other
conflict aborts that merge, prints the branch, the files and a summary of
their hunks, and exits 1. A replay's unknown conflict is first settled by an
earlier replay of the same commit (found by its `cherry-pick -x` line in the
worktree's HEAD, the local `rebase/<BASE>/*` branches or the remote
integration branch); otherwise its cherry-pick is left in progress, so that a
person resolves and commits it there, and the next run reuses that commit.
A replay resolution, by rerere or by an earlier replay, that is the replayed
commit's whole file while BASE's file differs from the commit's parent file is
refused as an unknown conflict (the source file was copied instead of applying
the change; `--allow-whole-copy PATH` lets one through). After a replay, every
path BASE has outside the Cosmyx-owned paths that changed by more than
`--drift-threshold` lines (default 40) against BASE is listed in a drift
warning table, except the paths of DRIFT_ALLOWED; `--strict-drift` makes that
an error (exit 1, nothing pushed).
Nothing is pushed unless `--push`, which pushes the branch (never the
`rebase/<BASE>/*` branches) and
`cosmyx-ci/<BASE>` (BASE's commit, the base of the build pull request)
atomically, each with force-with-lease on its old remote tip. `--build` builds
through a never-merged draft pull request from the branch into
`cosmyx-ci/<BASE>`: the "Cosmyx dev build" workflow runs on pull requests to
`cosmyx-ci/**`. The pull request is created after the push (its opening starts
the run) or, when already open, reused (the push started the run); open ones
from the same branch into another `cosmyx-ci/` base are closed before the push
so they do not build too. Pull requests from other branches are never touched.
`--os LIST` (comma list of linux, windows, macos-arm64, macos-x86_64) sets the
pull request's `build:*` labels, which pick the OSes the workflow builds, to
exactly that list: on a reused pull request before the push, so that the push
builds that set; on a new one at its creation. Without `--os` the labels are
left as they are (a new pull request has none: the workflow's default set).

`rebase-check` is a dry run: in a temporary worktree, it replays each branch's
own commits onto `refs/tags/upstream/TAG` (stacked children onto their
replayed parent) with the same auto-resolutions, and prints a table. No
branch is created, moved or pushed; the temporary worktree is always removed.

Exit codes: 0 done, 1 unknown conflict or strict drift (integrate) or
conflicts found (rebase-check), 2 usage or setup error.
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
# Branches a build pull request targets; "Cosmyx dev build" triggers on pull requests to them.
CI_BASE_PREFIX = "cosmyx-ci/"
DEV_BUILD_WORKFLOW = "cosmyx-dev-build.yml"
# Pull request labels that pick the OSes of a dev build (decision 0218), in
# the order --os documents them.
BUILD_LABEL_PREFIX = "build:"
BUILD_OSES = ("linux", "windows", "macos-arm64", "macos-x86_64")
BUILD_LABEL_COLOR = "1d76db"
# Settings for every merge or cherry-pick of a run: rerere replays recorded
# resolutions. The default conflict style is forced so that rerere finds the
# resolutions recorded by hand merges (a diff3 hunk has another conflict id);
# the resolvers get the diff3 form of a file by `checkout --conflict=diff3`.
RUN_CONFIG = ["-c", "rerere.enabled=true", "-c", "rerere.autoupdate=false", "-c", "merge.conflictStyle=merge",
              "-c", "core.editor=true"]
# Drift check of a replay (decision 0215): an upstream path that the replay
# changed by more lines than this against BASE is reported.
DRIFT_THRESHOLD = 40
# Upstream paths the Cosmyx branches legitimately change by more than that.
DRIFT_ALLOWED = (".github/workflows/build_orca.yml", "justfile")
# Paths owned by Cosmyx: changes there are not drift. Folders anywhere in a path:
OWNED_DIRS = ("cosmyx",)
# ...and top-level folders or files:
OWNED_TOP = ("wiki", ".claude", "cosmyx-src", "CHANGELOG.md")


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

    def blob_id(self, rev: str, path: str) -> str | None:
        completed = self.run("rev-parse", "-q", "--verify", f"{rev}:{path}", check=False)
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


def resolve_conflicts(git: Git, theirs_rev: str, brand_hook: BrandHook,
                      copy_guard: frozenset[str] | None = None) -> Outcome:
    """Resolve the conflicts of the merge or cherry-pick in progress in git.cwd.

    Known kinds are resolved and staged. Unknown ones are listed in the outcome
    and left as they are; the caller aborts or overrides them. With
    copy_guard (the paths allowed through), a rerere resolution that copied
    theirs_rev's whole file is unknown too (see copied_whole).
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
            if copy_guard is not None and path not in copy_guard and copied_whole(
                    git, path, theirs_rev, "HEAD", git.out("hash-object", "--", path)):
                unknown(path, [copy_message(git, path, theirs_rev, "the rerere resolution")])
                continue
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


def copied_whole(git: Git, path: str, source: str, before: str, resolved: str | None) -> bool:
    """True when `resolved` (a blob id) is `source`'s whole file put over another file.

    That is a resolution that copied the replayed commit's file instead of
    applying its change: the file at `before` (the HEAD the commit is replayed
    onto) differs from the commit's parent file, so applying the change cannot
    give the commit's file unless every difference of `before` was dropped.
    """
    theirs = git.blob_id(source, path)
    if theirs is None or resolved != theirs:
        return False
    return git.blob_id(before, path) != git.blob_id(f"{source}^", path)


def copy_message(git: Git, path: str, source: str, how: str) -> str:
    sha = git.out("rev-parse", source)
    return (f"{how} copied {sha[:10]}'s whole file instead of applying its change (the base file differs from "
            f"its parent's): run `git rerere forget {path}` in this worktree, resolve by hand, or pass "
            f"--allow-whole-copy {path} if that is intended")


def cosmyx_owned(path: str) -> bool:
    """True for a path Cosmyx owns: a cosmyx folder, a cosmyx- file, or an owned top-level entry."""
    parts = path.split("/")
    if parts[0] in OWNED_TOP:
        return True
    return any(part.lower() in OWNED_DIRS or part.lower().startswith("cosmyx-") for part in parts)


def drift_rows(git: Git, base: str, tip: str, threshold: int,
               allowed: tuple[str, ...] = DRIFT_ALLOWED) -> list[tuple[str, str, str]]:
    """(path, added, deleted) of each path of base outside Cosmyx's that tip changed by more than threshold lines.

    A binary change has no line count ("-") and is always reported.
    """
    in_base = set(git.out("ls-tree", "-r", "-z", "--name-only", base).split("\0"))
    rows = []
    for record in git.run("diff", "--numstat", "-z", "--no-renames", base, tip).stdout.split("\0"):
        if not record:
            continue
        added, deleted, path = record.split("\t", 2)
        if path not in in_base or path in allowed or cosmyx_owned(path):
            continue
        if added == "-" or int(added) + int(deleted) > threshold:
            rows.append((path, added, deleted))
    return sorted(rows)


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


def branch_holder(git: Git, branch: str) -> Path | None:
    """The worktree that has `branch` checked out, if any."""
    current = None
    for line in git.out("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            current = Path(line[len("worktree "):])
        elif line == f"branch refs/heads/{branch}":
            return current
    return None


def ensure_clean(wt: Git, why: str) -> None:
    if wt.out("status", "--porcelain") or wt.sha("MERGE_HEAD") or wt.sha("CHERRY_PICK_HEAD"):
        raise SetupError(f"{wt.cwd} is not clean ({why}): commit, stash or clean it first")


def set_branch(git: Git, branch: str, sha: str) -> None:
    """Point a local branch at sha; a worktree holding it is moved along, only when clean."""
    holder = branch_holder(git, branch)
    if holder is None:
        git.run("branch", "-f", branch, sha)
        return
    wt = Git(holder)
    ensure_clean(wt, f"it has {branch} checked out")
    wt.run("reset", "-q", "--hard", sha)


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
        ensure_clean(wt, f"it is the worktree of {branch}")
        wt.run("checkout", "-q", "-B", branch, base)
        return wt
    path.parent.mkdir(parents=True, exist_ok=True)
    git.run("worktree", "add", "-q", "-B", branch, str(path), base)
    return Git(path)


def base_name(base: str, remote: str) -> str:
    """BASE without its ref prefix: `origin/DEV` gives `DEV`, `refs/tags/v2.5.2` gives `v2.5.2`."""
    for prefix in (f"refs/remotes/{remote}/", "refs/heads/", "refs/tags/", f"{remote}/"):
        if base.startswith(prefix):
            return base[len(prefix):]
    return base


def checked_branch(git: Git, base: str, branch: str) -> str:
    if git.run("check-ref-format", f"refs/heads/{branch}", check=False).returncode != 0:
        raise SetupError(f"base {base} gives no valid branch name ({branch}): use a branch or tag name")
    return branch


def ci_base_branch(git: Git, base: str, remote: str) -> str:
    """`cosmyx-ci/<name>` for BASE: `origin/DEV` gives `cosmyx-ci/DEV`, tag `v2.5.2` gives `cosmyx-ci/v2.5.2`."""
    return checked_branch(git, base, CI_BASE_PREFIX + base_name(base, remote))


def integration_target(git: Git, base: str, remote: str, list_base: str) -> tuple[str, Path]:
    """The default integration branch and worktree for BASE.

    The list's base keeps `ci/cosmyx-integration` in `.worktrees/integration`;
    any other base gets `integration/<name>` in `.worktrees/integration-<name>`
    (`/` replaced by `-`), so that two bases never share a branch.
    """
    name = base_name(base, remote)
    if name == list_base:
        return INTEGRATION_BRANCH, INTEGRATION_WORKTREE
    branch = checked_branch(git, base, f"integration/{name}")
    return branch, Path(".worktrees") / ("integration-" + name.replace("/", "-"))


def gh_or_fail(gh: Callable, command: list[str], repo: str | None) -> str:
    command = command + (["--repo", repo] if repo else [])
    completed = gh(command)
    if completed.returncode != 0:
        raise SetupError(f"gh {' '.join(command)} failed: {completed.stderr.strip()}")
    return completed.stdout


def open_build_prs(gh: Callable, args, ci_branch: str, out) -> dict | None:
    """Before the push: return the open build pull request into ci_branch, if any.

    Open pull requests whose head is the branch, into another `cosmyx-ci/`
    base, are closed, so that the push does not start a build of them too.
    Any other pull request (another integration branch's) is left alone.
    """
    listed = json.loads(gh_or_fail(gh, ["pr", "list", "--head", args.branch, "--state", "open",
                                        "--json", "number,url,baseRefName,headRefName,labels"], args.repo) or "[]")
    reuse = None
    for pr in listed:
        if pr.get("headRefName", args.branch) != args.branch:
            continue
        base = pr.get("baseRefName", "")
        if base == ci_branch and reuse is None:
            reuse = pr
        elif base.startswith(CI_BASE_PREFIX):
            gh_or_fail(gh, ["pr", "close", str(pr["number"]), "--comment",
                            f"Superseded by an integration build on {ci_branch}."], args.repo)
            print(f"Closed stale build pull request {pr['url']} (base {base}).", file=out)
    return reuse


def parse_oses(value: str | None) -> list[str] | None:
    """The `build:*` labels --os asks for, in BUILD_OSES order; None without --os."""
    if value is None:
        return None
    oses = [item.strip() for item in value.split(",") if item.strip()]
    unknown = sorted(set(oses) - set(BUILD_OSES))
    if unknown or not oses:
        raise SetupError(f"--os takes a comma list among {', '.join(BUILD_OSES)}"
                         + (f"; unknown: {', '.join(unknown)}" if unknown else ""))
    return [BUILD_LABEL_PREFIX + name for name in BUILD_OSES if name in oses]


def ensure_build_labels(gh: Callable, args, labels: list[str], out) -> None:
    """Create the `build:*` labels the repository does not have yet."""
    listed = json.loads(gh_or_fail(gh, ["label", "list", "--search", BUILD_LABEL_PREFIX, "--limit", "100",
                                        "--json", "name"], args.repo) or "[]")
    existing = {label["name"] for label in listed}
    for label in labels:
        if label not in existing:
            gh_or_fail(gh, ["label", "create", label, "--color", BUILD_LABEL_COLOR, "--description",
                            f"Cosmyx dev build: build {label[len(BUILD_LABEL_PREFIX):]}"], args.repo)
            print(f"Created label {label}.", file=out)


def sync_build_labels(gh: Callable, args, pr: dict, labels: list[str], out) -> bool:
    """Set the pull request's `build:*` labels to exactly labels; True when they changed."""
    current = {label["name"] for label in pr.get("labels") or []
               if label["name"].startswith(BUILD_LABEL_PREFIX)}
    add = [label for label in labels if label not in current]
    remove = sorted(current - set(labels))
    if not add and not remove:
        return False
    command = ["pr", "edit", str(pr["number"])]
    if add:
        command += ["--add-label", ",".join(add)]
    if remove:
        command += ["--remove-label", ",".join(remove)]
    gh_or_fail(gh, command, args.repo)
    print(f"Build labels of {pr['url']}: {', '.join(labels)}.", file=out)
    return True


def create_build_pr(gh: Callable, args, ci_branch: str, base_label: str, labels: list[str] | None) -> str:
    body = (f"Build vehicle for `{args.branch}`, the integration of every Cosmyx pull request branch on "
            f"{base_label}. It runs the Cosmyx dev build (pull requests to `cosmyx-ci/**`; `build:*` labels "
            f"pick the OSes). Never merge this pull request: `{ci_branch}` only marks the base commit. "
            f"Rebuilt by `just cosmo-integrate`.")
    command = ["pr", "create", "--draft", "--head", args.branch, "--base", ci_branch,
               "--title", f"ci: integration build on {base_label} (never merge)", "--body", body]
    for label in labels or []:
        command += ["--label", label]
    return gh_or_fail(gh, command, args.repo).strip().splitlines()[-1]


def integrate(args, out=sys.stdout, brand_hook: BrandHook = run_branding_engine, gh: Callable | None = None) -> int:
    git = Git(Path(args.repo_root) if args.repo_root else Path.cwd())
    data, entries = load_branches(Path(args.data) if args.data else DATA_FILE)
    remote = data["remote"]
    entries = [entry for entry in entries if entry.name not in set(args.skip or [])]
    if args.build and not args.push:
        raise SetupError("--build needs --push")
    if args.os is not None and not args.build:
        raise SetupError("--os needs --build")
    labels = parse_oses(args.os)
    if not args.no_fetch:
        git.run("fetch", "-q", "--prune", remote)
    base = args.base or f"{remote}/{data['base']}"
    base_sha = git.sha(base)
    if not base_sha:
        raise SetupError(f"base {base} not found")
    ci_branch = ci_base_branch(git, args.base or data["base"], remote) if args.push else None
    default_branch, default_worktree = integration_target(git, args.base or data["base"], remote, data["base"]) \
        if not (args.branch and args.worktree) else (args.branch, Path(args.worktree))
    args.branch = args.branch or default_branch
    tips = {}
    for entry in entries:
        tips[entry.name] = git.sha(f"refs/remotes/{remote}/{entry.name}")
        if not tips[entry.name]:
            print(f"warning: {remote}/{entry.name} not found, skipped (not pushed yet?)", file=out)
    entries = [entry for entry in entries if tips[entry.name]]
    old_tip = git.sha(f"refs/remotes/{remote}/{args.branch}")
    worktree = main_root(git) / (args.worktree or default_worktree)
    holder = branch_holder(git, args.branch)
    if holder and holder.resolve() != worktree.resolve():
        if args.worktree:
            raise SetupError(f"{args.branch} is checked out in {holder}, not in {worktree}")
        # Reuse the worktree that already holds the branch (a hand-made
        # integration's): git refuses a branch checked out twice.
        print(f"{args.branch} is checked out in {holder}: that worktree is used.", file=out)
        worktree = holder
    replay_mode = base_name(args.base or data["base"], remote) != data["base"]
    resolved: dict[str, str] = {}
    if replay_mode:
        # Earlier replays that may carry hand resolutions: the worktree's HEAD
        # (a resolution just committed there), the local rebase branches, then
        # the remote integration branch.
        start = Git(worktree).sha("HEAD") if (worktree / ".git").exists() else None
        rebase_refs = git.out("for-each-ref", "--format=%(refname)",
                              f"refs/heads/rebase/{base_name(args.base, remote)}/").split()
        resolved = resolved_picks(git, ([start] if start else []) + rebase_refs
                                  + [f"refs/remotes/{remote}/{args.branch}"], base_sha)
    wt = prepare_worktree(git, worktree, args.branch, base_sha)
    train = args.train or (f"refs/remotes/{remote}/{args.branch}" if not args.no_train else None)
    if train and git.sha(train):
        train_rerere(wt, train, base_sha, out)
        wt.run("checkout", "-q", "-f", "-B", args.branch, base_sha)
    print(f"{args.branch} reset to {base} ({base_sha[:10]}) in {wt.cwd}", file=out)
    rows: list[tuple[str, str, str]] = []
    sources = {entry.name: f"{remote}/{entry.name}" for entry in entries}
    notes: dict[str, str] = {}
    if replay_mode:
        sources, notes, stopped = replay_branches(git, wt, data, entries, base_sha,
                                                  base_name(args.base, remote), brand_hook, out, resolved,
                                                  args.branch, frozenset(args.allow_whole_copy or ()))
        if stopped:
            return 1
        wt.run("checkout", "-q", "-f", "-B", args.branch, base_sha)
    for entry in entries:
        if entry.name not in sources:
            rows.append((entry.name, tips[entry.name][:10], notes[entry.name]))
            continue
        prefix = notes[entry.name] + "; merge " if entry.name in notes else ""
        result = wt.run("merge", "--no-ff", "--no-commit", sources[entry.name], check=False)
        if not wt.sha("MERGE_HEAD"):
            if result.returncode != 0:
                raise SetupError(f"merge of {entry.name} failed:\n{result.stdout}{result.stderr}")
            rows.append((entry.name, tips[entry.name][:10], prefix + "already in"))
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
                     prefix + ("auto-resolved: " + ", ".join(outcome.kinds) if outcome.kinds else "clean")))
    tip = wt.out("rev-parse", "HEAD")
    table(rows, ("Branch", "Tip", "Result"), out)
    print(f"{args.branch} = {tip[:10]} (remote {old_tip[:10] if old_tip else 'absent'})", file=out)
    if replay_mode:
        drift = drift_rows(wt, base_sha, tip, args.drift_threshold)
        if drift:
            print(f"DRIFT WARNING: {len(drift)} path(s) of {base} changed by more than {args.drift_threshold} "
                  f"lines (a replay may have copied a source file whole; check them):", file=out)
            table(drift, ("Path", "Added", "Deleted"), out)
            if args.strict_drift:
                print(f"Stopped (--strict-drift): {args.branch} holds the result; nothing pushed.", file=out)
                return 1
    if not args.push:
        print("Not pushed (use --push).", file=out)
        return 0
    gh = gh or run_gh
    reuse = open_build_prs(gh, args, ci_branch, out) if args.build else None
    relabeled = False
    if labels is not None:
        ensure_build_labels(gh, args, labels, out)
        if reuse:
            # Before the push, so that the push builds the new set.
            relabeled = sync_build_labels(gh, args, reuse, labels, out)
    old_ci = git.sha(f"refs/remotes/{remote}/{ci_branch}")
    wt.run("push", "--atomic", f"--force-with-lease=refs/heads/{args.branch}:{old_tip or ''}",
           f"--force-with-lease=refs/heads/{ci_branch}:{old_ci or ''}", remote,
           f"{args.branch}:refs/heads/{args.branch}", f"{base_sha}:refs/heads/{ci_branch}")
    print(f"Pushed {args.branch} {tip[:10]} and {ci_branch} {base_sha[:10]}.", file=out)
    if not args.build:
        return 0
    base_label = ci_branch[len(CI_BASE_PREFIX):]
    if reuse:
        url = reuse["url"]
        if tip != old_tip:
            started = "the push started the Cosmyx dev build"
        elif relabeled:
            started = "the head did not move; the label change started the Cosmyx dev build"
        else:
            started = "the head did not move, so no new run: rerun the last one with gh run rerun"
        print(f"Build pull request (reused): {url}; {started}.", file=out)
    else:
        url = create_build_pr(gh, args, ci_branch, base_label, labels)
        print(f"Build pull request (created, draft): {url}; its opening started the Cosmyx dev build.", file=out)
    repo = f" --repo {args.repo}" if args.repo else ""
    print(f"Run: {url}/checks, or gh run list --workflow {DEV_BUILD_WORKFLOW} --branch {args.branch}{repo}",
          file=out)
    return 0


def replay_branches(git: Git, wt: Git, data: dict, entries: list[Entry], base_sha: str, name: str,
                    brand_hook: BrandHook, out, resolved: dict[str, str], branch: str,
                    allowed_copies: frozenset[str] = frozenset()) -> tuple[dict[str, str], dict[str, str], bool]:
    """Replay each branch's own commits onto BASE as `rebase/<name>/<branch>`, in list order.

    Returns (branch to merge per entry, table note per entry, stopped). A
    branch whose parent was not replayed gets a note and no branch to merge.
    On an unknown conflict the cherry-pick is left in progress in wt, the
    report says how to record its resolution, and stopped is True.
    """
    remote = data["remote"]
    dev = git.sha(f"refs/remotes/{remote}/{data['base']}")
    if not dev:
        raise SetupError(f"{remote}/{data['base']} not found")
    sources: dict[str, str] = {}
    notes: dict[str, str] = {}
    replayed: dict[str, str] = {}
    for entry in entries:
        tip = git.sha(f"refs/remotes/{remote}/{entry.name}")
        parent, commits = own_commits(git, data, entry, tip, dev)
        new_base = base_sha if parent is None else replayed.get(parent)
        if commits is None or not new_base:
            notes[entry.name] = f"SKIPPED (parent {parent} not replayed)"
            continue
        # On the integration branch, not detached: a stopped run leaves the
        # branch in this worktree, so that the next run finds it there.
        wt.run("checkout", "-q", "-f", "-B", branch, new_base)
        try:
            kinds, _ = replay(wt, commits, brand_hook, strict=True, resolved=resolved, allowed_copies=allowed_copies)
        except ReplayStopped as stop:
            subject = git.out("log", "-1", "--format=%s", stop.commit)
            report_unknown(f"{remote}/{entry.name} ({tip[:10]}), replaying {stop.commit[:10]} \"{subject}\"",
                           stop.outcome, out)
            print(f"Stopped: the cherry-pick is left in progress in {wt.cwd}. Resolve it there (any file the "
                  f"commit needs on this base), `git add` the files, run `git -c core.editor=true cherry-pick "
                  f"--continue` (it keeps the \"{PICKED}...)\" line), then run again: that commit is reused for "
                  f"{stop.commit[:10]} on this base, now and in later runs once pushed (rerere also records the "
                  f"content conflicts it saw). Nothing pushed.", file=out)
            return sources, notes, True
        head = wt.out("rev-parse", "HEAD")
        replayed[entry.name] = head
        sources[entry.name] = f"rebase/{name}/{entry.name}"
        set_branch(git, sources[entry.name], head)
        notes[entry.name] = f"replayed {len(commits)}" + (f" (auto-resolved: {', '.join(kinds)})" if kinds else "")
    return sources, notes, False


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


# Line `cherry-pick -x` adds to a replayed commit: it names the original commit.
PICKED = "(cherry picked from commit "


def resolved_picks(git: Git, refs: list[str], base_sha: str) -> dict[str, str]:
    """Map each original commit to an earlier replay of it, from refs (first ref wins).

    A replay is found by the `cherry-pick -x` line of its message, so a
    branch commit that was rewritten since (new sha) gets no stale match.
    """
    found: dict[str, str] = {}
    for ref in refs:
        if not git.sha(ref):
            continue
        log = git.run("log", "--no-merges", "--format=%H%x00%B%x1e", ref, f"^{base_sha}").stdout
        for record in log.split("\x1e"):
            sha, _, body = record.strip().partition("\0")
            for line in body.splitlines():
                line = line.strip()
                if line.startswith(PICKED) and line.endswith(")"):
                    found.setdefault(line[len(PICKED):-1], sha)
    return found


class ReplayStopped(Exception):
    """An unknown conflict while replaying `commit`; the cherry-pick is left in progress."""

    def __init__(self, commit: str, outcome: Outcome) -> None:
        super().__init__(commit)
        self.commit = commit
        self.outcome = outcome


def own_commits(git: Git, data: dict, entry: Entry, tip: str, dev: str) -> tuple[str | None, list[str] | None]:
    """(parent the branch is replayed onto, its own commits oldest first).

    The foundation's own commits are those after its merge base with DEV and
    it has no parent (None); any other branch's are those after its merge base
    with its parent, the foundation for a DEV-parented branch. The commits are
    None when the parent is not on the remote.
    """
    remote, foundation = data["remote"], data["foundation"]
    if entry.name == foundation:
        old_base, parent = git.out("merge-base", tip, dev), None
    else:
        parent = foundation if entry.parent == data["base"] else entry.parent
        parent_tip = git.sha(f"refs/remotes/{remote}/{parent}")
        if not parent_tip:
            return parent, None
        old_base = git.out("merge-base", tip, parent_tip)
    return parent, git.out("rev-list", "--reverse", "--no-merges", f"{old_base}..{tip}").split()


def pick(wt: Git, commit: str, brand_hook: BrandHook, record: bool,
         copy_guard: frozenset[str] | None = None) -> Outcome | None:
    """Cherry-pick one commit onto HEAD: None when clean, else the conflict outcome."""
    result = wt.run("cherry-pick", "--allow-empty", "--empty=drop", *(["-x"] if record else []), commit, check=False)
    if result.returncode == 0:
        return None
    if not wt.sha("CHERRY_PICK_HEAD"):
        raise SetupError(f"cherry-pick {commit[:10]} failed:\n{result.stderr}")
    return resolve_conflicts(wt, "CHERRY_PICK_HEAD", brand_hook, copy_guard)


def replay(wt: Git, commits: list[str], brand_hook: BrandHook, strict: bool = False,
           resolved: dict[str, str] | None = None,
           allowed_copies: frozenset[str] = frozenset()) -> tuple[list[str], list[str]]:
    """Cherry-pick commits onto HEAD; return (auto-resolution kinds, conflicting files).

    An unknown conflict is overridden with the commit's side (dry run), or,
    when strict, settled by an earlier replay of the commit (from resolved,
    which carries a hand resolution forward), or else raises ReplayStopped
    with the cherry-pick left in progress. Strict picks record the original
    commit with `-x`, so that a hand-resolved commit can be found again.
    Strict picks also refuse a resolution that copied the commit's whole file
    (see copied_whole), unless the path is in allowed_copies.
    """
    kinds: list[str] = []
    conflicts: list[str] = []
    guard = allowed_copies if strict else None
    for commit in commits:
        outcome = pick(wt, commit, brand_hook, record=strict, copy_guard=guard)
        if outcome is None:
            continue
        if outcome.unknown and strict and commit in (resolved or {}):
            # Its own message already names the original commit: no second -x line.
            conflicted = [path for path, _ in outcome.unknown]
            before = wt.out("rev-parse", "HEAD")
            wt.run("cherry-pick", "--abort")
            outcome = pick(wt, resolved[commit], brand_hook, record=False, copy_guard=guard)
            if "earlier resolution" not in kinds:
                kinds.append("earlier resolution")
            if outcome is None:
                reject_copies(wt, commit, resolved[commit], conflicted, before, brand_hook, guard)
                continue
            if not outcome.unknown:
                kinds.extend(kind for kind in outcome.kinds if kind not in kinds)
                commit_pick(wt)
                reject_copies(wt, commit, resolved[commit], conflicted, before, brand_hook, guard)
                continue
        kinds.extend(kind for kind in outcome.kinds if kind not in kinds)
        if outcome.unknown and strict:
            raise ReplayStopped(commit, outcome)
        if outcome.unknown:
            paths = [path for path, _ in outcome.unknown]
            conflicts.extend(f"{path} ({commit[:10]})" for path in paths)
            take_theirs(wt, paths)
        commit_pick(wt)
    return kinds, conflicts


def commit_pick(wt: Git) -> None:
    """Commit the resolved cherry-pick in progress, or skip it when it changes nothing."""
    if wt.run("diff", "--cached", "--quiet", check=False).returncode == 0:
        wt.run("cherry-pick", "--skip")
    else:
        wt.run("commit", "-q", "--no-verify", "--no-edit", "--allow-empty")


def reject_copies(wt: Git, commit: str, earlier: str, paths: list[str], before: str, brand_hook: BrandHook,
                  allowed: frozenset[str]) -> None:
    """Undo an earlier replay that copied `commit`'s whole file at one of its conflicted paths.

    The replay just committed on `before` is dropped and `commit` is picked
    again, left in progress for a hand resolution; raises ReplayStopped.
    """
    copied = [path for path in paths if path not in allowed
              and copied_whole(wt, path, commit, before, wt.blob_id("HEAD", path))]
    if not copied:
        return
    wt.run("reset", "-q", "--hard", before)
    outcome = pick(wt, commit, brand_hook, record=True, copy_guard=allowed) or Outcome()
    how = f"the earlier resolution {earlier[:10]}"
    notes = {path: copy_message(wt, path, commit, how) for path in copied}
    outcome.unknown = [(path, why + ([notes.pop(path)] if path in notes else [])) for path, why in outcome.unknown]
    outcome.unknown += [(path, [note]) for path, note in notes.items()]
    raise ReplayStopped(commit, outcome)


def rebase_check(args, out=sys.stdout, brand_hook: BrandHook = run_branding_engine) -> int:
    git = Git(Path(args.repo_root) if args.repo_root else Path.cwd())
    data, entries = load_branches(Path(args.data) if args.data else DATA_FILE)
    remote = data["remote"]
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
                # Not pushed yet: a warning, not a failure; its children show as SKIPPED.
                rows.append((entry.name, "-", "missing on the remote, skipped", ""))
                continue
            parent, commits = own_commits(git, data, entry, tip, dev)
            new_base = onto if parent is None else replayed.get(parent)
            if commits is None or not new_base:
                rows.append((entry.name, tip[:10], f"SKIPPED (parent {parent} not replayed)", ""))
                continue
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
    return 1 if any(row[2].startswith(("CONFLICT", "SKIPPED")) for row in rows) else 0


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
    one.add_argument("--branch", help=f"integration branch (default: {INTEGRATION_BRANCH} for the list's base, "
                                      "integration/<BASE> for any other)")
    one.add_argument("--worktree", help=f"worktree path under the main checkout (default: {INTEGRATION_WORKTREE} "
                                        "for the list's base, .worktrees/integration-<BASE> for any other)")
    one.add_argument("--allow-whole-copy", action="append", metavar="PATH",
                     help="replay mode: accept a resolution that copies the replayed commit's whole file at PATH "
                          "(repeatable)")
    one.add_argument("--drift-threshold", type=int, default=DRIFT_THRESHOLD, metavar="LINES",
                     help=f"replay mode: report upstream paths changed by more lines than this against BASE "
                          f"(default {DRIFT_THRESHOLD})")
    one.add_argument("--strict-drift", action="store_true",
                     help="replay mode: exit 1 and push nothing when the drift table is not empty")
    one.add_argument("--no-train", action="store_true",
                     help="do not teach rerere from the current remote integration branch")
    one.add_argument("--push", action="store_true",
                     help=f"push the branch and {CI_BASE_PREFIX}<BASE> with --force-with-lease on their old tips")
    one.add_argument("--build", action="store_true",
                     help=f"with --push, build through a draft pull request into {CI_BASE_PREFIX}<BASE>")
    one.add_argument("--os", metavar="LIST",
                     help=f"with --build, build only these OSes (comma list among {', '.join(BUILD_OSES)}): "
                          f"sets the build pull request's {BUILD_LABEL_PREFIX}* labels to exactly that list")
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
