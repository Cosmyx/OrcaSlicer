"""Keep the Cosmyx fork in step with upstream OrcaSlicer.

Subcommands:

- mirror: make the Orca-Upstream branch an exact copy of upstream main.
  Skips everything when both tips are already equal.
- mixed: rebuild the MIXED branch as DEV merged with Orca-Upstream. The merge
  commit carries the trailer `Cosmyx-Mixed: base=<sha> upstream=<sha>`, so a
  run whose inputs did not move pushes nothing. A conflict lists the files in
  the job summary and as annotations and exits with code 2: with the zero
  conflict rule, a conflict on MIXED is a bug to fix on DEV.
- workflow-policy: check that every scheduled workflow is either allowed or
  disabled by .github/cosmyx/workflow-policy.json; with --apply, disable the
  listed bots on the repository through the GitHub API (idempotent).

Standard library only. Every git and gh call goes through subprocess with an
argument list, so the script behaves the same on Linux, macOS and Windows.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = REPO_ROOT / ".github" / "cosmyx" / "workflow-policy.json"
DEFAULT_WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898283+github-actions[bot]@users.noreply.github.com"

TRAILER_KEY = "Cosmyx-Mixed"
TRAILER_RE = re.compile(
    r"^" + TRAILER_KEY + r":\s*base=(?P<base>[0-9a-f]{40,64})\s+upstream=(?P<upstream>[0-9a-f]{40,64})\s*$",
    re.MULTILINE,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFLICT = 2


class SyncError(RuntimeError):
    """A failure that ends the run with a clear message."""


# ---------------------------------------------------------------------------
# Output helpers (GitHub Actions aware, plain text elsewhere)
# ---------------------------------------------------------------------------


def _append(env_name: str, text: str) -> None:
    target = os.environ.get(env_name)
    if not target:
        return
    with open(target, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_summary(markdown: str) -> None:
    """Append markdown to the job summary when running in GitHub Actions."""
    _append("GITHUB_STEP_SUMMARY", markdown.rstrip("\n") + "\n")


def set_output(name: str, value: str) -> None:
    """Set a step output when running in GitHub Actions."""
    _append("GITHUB_OUTPUT", f"{name}={value}\n")


def _escape_property(value: str) -> str:
    # Workflow command property escaping, see the GitHub workflow commands docs.
    return (
        value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(":", "%3A").replace(",", "%2C")
    )


def annotate(level: str, message: str, file: str | None = None, title: str | None = None) -> None:
    """Print a workflow command annotation (::error, ::warning, ::notice)."""
    props = []
    if file:
        props.append(f"file={_escape_property(file)}")
    if title:
        props.append(f"title={_escape_property(title)}")
    prop_text = (" " + ",".join(props)) if props else ""
    print(f"::{level}{prop_text}::{message}", flush=True)


# ---------------------------------------------------------------------------
# git plumbing
# ---------------------------------------------------------------------------


def bot_env() -> dict[str, str]:
    """Environment for git commands, with the bot identity unless one is set."""
    env = dict(os.environ)
    env.setdefault("GIT_AUTHOR_NAME", BOT_NAME)
    env.setdefault("GIT_AUTHOR_EMAIL", BOT_EMAIL)
    env.setdefault("GIT_COMMITTER_NAME", env["GIT_AUTHOR_NAME"])
    env.setdefault("GIT_COMMITTER_EMAIL", env["GIT_AUTHOR_EMAIL"])
    # Never stop on a credential prompt in CI.
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    return env


def git(args: Sequence[str], cwd: Path | None = None, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(cwd) if cwd else None,
        env=bot_env(),
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if check and completed.returncode != 0:
        raise SyncError(f"git {redact(' '.join(args))} failed: {redact(completed.stderr.strip())}")
    return completed


def redact(text: str) -> str:
    """Hide credentials embedded in https URLs."""
    return re.sub(r"(https?://)[^/@\s]+@", r"\1***@", text)


def remote_sha(remote: str, branch: str) -> str | None:
    """Tip of a branch on a remote, or None when it does not exist."""
    out = git(["ls-remote", remote, f"refs/heads/{branch}"]).stdout.strip()
    if not out:
        return None
    return out.splitlines()[0].split()[0]


def init_work_repo(work_dir: Path | None) -> tuple[Path, Callable[[], None]]:
    """A scratch bare repository to fetch into; returns it and its cleanup."""
    if work_dir is not None:
        work_dir.mkdir(parents=True, exist_ok=True)
        path = work_dir
        cleanup: Callable[[], None] = lambda: None
    else:
        path = Path(tempfile.mkdtemp(prefix="cosmyx-sync-"))
        cleanup = lambda: shutil.rmtree(path, ignore_errors=True)
    if not (path / "HEAD").exists():
        git(["init", "-q", "--bare", str(path)])
    return path, cleanup


def fetch(repo: Path, remote: str, branch: str, local_ref: str) -> None:
    git(["fetch", "-q", "--no-tags", remote, f"+refs/heads/{branch}:{local_ref}"], cwd=repo)


def push(repo: Path, remote: str, source: str, branch: str) -> None:
    git(["push", "-q", "--force", remote, f"{source}:refs/heads/{branch}"], cwd=repo)


# ---------------------------------------------------------------------------
# mirror
# ---------------------------------------------------------------------------


@dataclass
class MirrorResult:
    changed: bool
    before: str | None
    after: str


def mirror(upstream: str, upstream_branch: str, origin: str, target: str, dry_run: bool = False,
           work_dir: Path | None = None) -> MirrorResult:
    upstream_tip = remote_sha(upstream, upstream_branch)
    if upstream_tip is None:
        raise SyncError(f"could not resolve {redact(upstream)} {upstream_branch}")
    current = remote_sha(origin, target)
    print(f"upstream {upstream_branch}: {upstream_tip}")
    print(f"origin {target}: {current or '<missing>'}")
    if current == upstream_tip:
        print(f"{target} is already up to date.")
        set_output("changed", "false")
        set_output("sha", upstream_tip)
        return MirrorResult(False, current, upstream_tip)

    repo, cleanup = init_work_repo(work_dir)
    try:
        if current:
            # Fetch our current copy first so only the new upstream objects are downloaded.
            fetch(repo, origin, target, "refs/cosmyx/current")
        fetch(repo, upstream, upstream_branch, "refs/cosmyx/upstream")
        if dry_run:
            print(f"Dry run: would force-push {upstream_tip} to {target}.")
        else:
            # Force: the branch mirrors upstream exactly, even after an upstream history rewrite.
            push(repo, origin, "refs/cosmyx/upstream", target)
    finally:
        cleanup()
    set_output("changed", "false" if dry_run else "true")
    set_output("sha", upstream_tip)
    verb = "would move" if dry_run else "moved"
    write_summary(f"### {target} {verb}\n`{current or 'none'}` -> `{upstream_tip}`\n")
    return MirrorResult(not dry_run, current, upstream_tip)


# ---------------------------------------------------------------------------
# mixed
# ---------------------------------------------------------------------------


@dataclass
class MixedResult:
    status: str  # "unchanged", "updated", "dry-run" or "conflict"
    base: str
    upstream: str
    commit: str | None = None
    conflicts: tuple[str, ...] = ()


def parse_trailer(message: str) -> tuple[str, str] | None:
    """(base, upstream) recorded in a MIXED commit message, if any."""
    matches = list(TRAILER_RE.finditer(message))
    if not matches:
        return None
    last = matches[-1]
    return last.group("base"), last.group("upstream")


def mixed_message(base_branch: str, base: str, upstream_branch: str, upstream: str) -> str:
    return (
        f"Merge {upstream_branch} into {base_branch} for MIXED\n"
        "\n"
        f"Built by the Cosmyx upstream sync: {base_branch} at {base[:12]} merged with\n"
        f"{upstream_branch} at {upstream[:12]}. This branch is force-pushed on every\n"
        "run; never commit on it.\n"
        "\n"
        f"{TRAILER_KEY}: base={base} upstream={upstream}\n"
    )


def merge_trees(repo: Path, base: str, upstream: str) -> tuple[str | None, list[str]]:
    """Merge without a working tree. Returns (tree, []) or (None, conflicted files)."""
    completed = git(["merge-tree", "--write-tree", "--name-only", "--no-messages", base, upstream],
                    cwd=repo, check=False)
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if completed.returncode == 0 and lines:
        return lines[0].strip(), []
    if completed.returncode == 1 and lines:
        # First line is the tree with conflict markers, then one conflicted path per line.
        return None, sorted(dict.fromkeys(lines[1:]))
    raise SyncError(f"git merge-tree failed: {completed.stderr.strip()}")


def report_conflicts(base_branch: str, base: str, upstream_branch: str, upstream: str, files: Sequence[str]) -> None:
    for name in files:
        annotate("error", f"{upstream_branch} conflicts with {base_branch} in {name}", file=name,
                 title="Merge conflict")
    rows = "\n".join(f"| `{name}` |" for name in files)
    write_summary(
        f"### MIXED: merge conflict\n"
        f"{upstream_branch} `{upstream[:12]}` does not merge cleanly into {base_branch} `{base[:12]}`.\n"
        "Zero conflicts with upstream is a hard rule: fix the hooks on "
        f"{base_branch}.\n\n| Conflicted file |\n|---|\n{rows}\n"
    )
    print(f"Merge conflict in {len(files)} file(s):")
    for name in files:
        print(f"  {name}")


def mixed(origin: str, base_branch: str, upstream_branch: str, target: str, dry_run: bool = False,
          work_dir: Path | None = None) -> MixedResult:
    repo, cleanup = init_work_repo(work_dir)
    try:
        fetch(repo, origin, base_branch, "refs/cosmyx/base")
        fetch(repo, origin, upstream_branch, "refs/cosmyx/upstream")
        base = git(["rev-parse", "refs/cosmyx/base"], cwd=repo).stdout.strip()
        upstream = git(["rev-parse", "refs/cosmyx/upstream"], cwd=repo).stdout.strip()
        print(f"{base_branch}: {base}")
        print(f"{upstream_branch}: {upstream}")
        set_output("base", base)
        set_output("upstream", upstream)

        previous = remote_sha(origin, target)
        if previous:
            fetch(repo, origin, target, "refs/cosmyx/mixed")
            message = git(["log", "-1", "--format=%B", "refs/cosmyx/mixed"], cwd=repo).stdout
            if parse_trailer(message) == (base, upstream):
                print(f"{target} already merges these tips; nothing to do.")
                set_output("changed", "false")
                set_output("sha", previous)
                write_summary(f"### {target} unchanged\nStill `{previous[:12]}`.\n")
                return MixedResult("unchanged", base, upstream, previous)

        tree, conflicts = merge_trees(repo, base, upstream)
        if tree is None:
            report_conflicts(base_branch, base, upstream_branch, upstream, conflicts)
            set_output("changed", "false")
            return MixedResult("conflict", base, upstream, None, tuple(conflicts))

        # Always two parents, even when upstream is already contained in the base,
        # so the trailer and the history read the same on every run.
        commit = git(["commit-tree", tree, "-p", base, "-p", upstream, "-F", "-"], cwd=repo,
                     input_text=mixed_message(base_branch, base, upstream_branch, upstream)).stdout.strip()
        if dry_run:
            print(f"Dry run: would force-push {commit} to {target}.")
            set_output("changed", "false")
            status = "dry-run"
        else:
            push(repo, origin, commit, target)
            set_output("changed", "true")
            status = "updated"
        set_output("sha", commit)
        verb = "would be" if dry_run else "rebuilt as"
        write_summary(
            f"### {target} {verb} `{commit[:12]}`\n"
            f"{base_branch} `{base[:12]}` + {upstream_branch} `{upstream[:12]}`, no conflict.\n"
        )
        return MixedResult(status, base, upstream, commit)
    finally:
        cleanup()


# ---------------------------------------------------------------------------
# workflow-policy
# ---------------------------------------------------------------------------

_SCHEDULE_KEY_RE = re.compile(r"^\s*-?\s*['\"]?schedule['\"]?\s*:")
_ON_FLOW_RE = re.compile(r"^['\"]?on['\"]?\s*:\s*(\[.*\]|\S.*)$")


def _strip_comment(line: str) -> str:
    # A '#' starts a comment at the line start or after whitespace (YAML rule).
    match = re.search(r"(^|\s)#", line)
    return line[: match.start()] if match else line


def is_scheduled(text: str) -> bool:
    """True when a workflow declares a schedule trigger (comments ignored)."""
    for raw in text.splitlines():
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        if _SCHEDULE_KEY_RE.match(line):
            return True
        flow = _ON_FLOW_RE.match(line)
        if flow and re.search(r"\bschedule\b", flow.group(1)):
            return True
    return False


def scheduled_workflows(workflows_dir: Path) -> list[str]:
    names = []
    for path in sorted(workflows_dir.iterdir()):
        if path.suffix.lower() in (".yml", ".yaml") and path.is_file():
            if is_scheduled(path.read_text(encoding="utf-8")):
                names.append(path.name)
    return names


@dataclass
class Policy:
    disable: list[str]
    allow_scheduled: list[str]
    must_stay_enabled: list[str]


def load_policy(path: Path) -> Policy:
    data = json.loads(path.read_text(encoding="utf-8"))
    policy = Policy(
        disable=list(data.get("disable", [])),
        allow_scheduled=list(data.get("allow_scheduled", [])),
        must_stay_enabled=list(data.get("must_stay_enabled", [])),
    )
    return policy


def check_policy(policy: Policy, scheduled: Sequence[str]) -> list[str]:
    """Problems with the policy against the scheduled workflows; empty when fine."""
    problems = []
    both = sorted(set(policy.disable) & set(policy.allow_scheduled))
    for name in both:
        problems.append(f"{name} is both allowed and disabled")
    for name in sorted(set(policy.disable) & set(policy.must_stay_enabled)):
        problems.append(f"{name} must stay enabled but is in the disable list")
    known = set(policy.disable) | set(policy.allow_scheduled)
    for name in scheduled:
        if name not in known:
            problems.append(
                f"{name} has a schedule trigger but is in neither allow_scheduled nor disable "
                "of .github/cosmyx/workflow-policy.json"
            )
    return problems


Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]


def run_gh(args: Sequence[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8", check=False)


def _gh_error_text(completed: subprocess.CompletedProcess) -> str:
    return f"{completed.stdout}\n{completed.stderr}".strip()


def apply_policy(policy: Policy, repo: str, runner: Runner = run_gh) -> list[str]:
    """Disable every listed workflow that is active. Returns one line per workflow.

    Idempotent: a workflow that is already disabled, inactive, or not registered
    on the repository yet (404) is left as it is and retried on the next run.
    """
    lines = []
    for name in policy.disable:
        endpoint = f"repos/{repo}/actions/workflows/{name}"
        state_call = runner(["api", endpoint, "--jq", ".state"])
        if state_call.returncode != 0:
            text = _gh_error_text(state_call)
            if "404" in text or "Not Found" in text:
                lines.append(f"{name}: not registered on {repo} yet, retried next run")
                continue
            raise SyncError(f"could not read the state of {name}: {text}")
        state = state_call.stdout.strip()
        if state != "active":
            lines.append(f"{name}: already {state or 'unknown'}")
            continue
        disable_call = runner(["api", "-X", "PUT", f"{endpoint}/disable"])
        if disable_call.returncode != 0:
            text = _gh_error_text(disable_call)
            if "not active" in text.lower():
                lines.append(f"{name}: not active")
                continue
            if "404" in text or "Not Found" in text:
                lines.append(f"{name}: not registered on {repo} yet, retried next run")
                continue
            raise SyncError(f"could not disable {name}: {text}")
        lines.append(f"{name}: disabled")
    for name in policy.must_stay_enabled:
        state_call = runner(["api", f"repos/{repo}/actions/workflows/{name}", "--jq", ".state"])
        state = state_call.stdout.strip() if state_call.returncode == 0 else "unknown"
        if state != "active":
            annotate("warning", f"{name} must stay enabled but its state is {state}",
                     title="Workflow policy")
        lines.append(f"{name}: must stay enabled ({state})")
    return lines


def workflow_policy(policy_path: Path, workflows_dir: Path, apply: bool, repo: str | None,
                    runner: Runner = run_gh) -> int:
    policy = load_policy(policy_path)
    scheduled = scheduled_workflows(workflows_dir)
    print("Scheduled workflows: " + (", ".join(scheduled) or "none"))
    problems = check_policy(policy, scheduled)
    for problem in problems:
        annotate("error", problem, title="Workflow policy")
    if problems:
        write_summary("### Workflow policy failed\n" + "\n".join(f"- {p}" for p in problems) + "\n")
        return EXIT_ERROR
    print("Workflow policy: every scheduled workflow is allowed or disabled.")
    if apply:
        if not repo:
            raise SyncError("--apply needs --repo or GITHUB_REPOSITORY")
        lines = apply_policy(policy, repo, runner)
        for line in lines:
            print(line)
        write_summary("### Workflow policy applied\n" + "\n".join(f"- {line}" for line in lines) + "\n")
    return EXIT_OK


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------


def github_url(repo: str, token: str | None) -> str:
    if token:
        return f"https://x-access-token:{token}@github.com/{repo}.git"
    return f"https://github.com/{repo}.git"


def resolve_origin(args: argparse.Namespace) -> str:
    """The origin remote: --origin as given, else the current repository with a token."""
    if args.origin:
        return args.origin
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo:
        raise SyncError("--origin is required outside GitHub Actions")
    token = os.environ.get("UPSTREAM_SYNC_TOKEN")
    if not token:
        annotate("warning", "UPSTREAM_SYNC_TOKEN is not set; using GITHUB_TOKEN, which cannot push "
                            "commits that change .github/workflows.", title="Upstream sync token")
        token = os.environ.get("GITHUB_TOKEN")
    return github_url(repo, token)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--origin", help="URL or path of the fork (default: GITHUB_REPOSITORY with a token)")
    common.add_argument("--dry-run", action="store_true", help="compute everything, push nothing")
    common.add_argument("--work-dir", type=Path, help="scratch bare repository to reuse (default: a temp dir)")

    m = sub.add_parser("mirror", parents=[common], help="mirror upstream main into Orca-Upstream")
    m.add_argument("--upstream", default="https://github.com/OrcaSlicer/OrcaSlicer.git")
    m.add_argument("--upstream-branch", default="main")
    m.add_argument("--target", default="Orca-Upstream")

    x = sub.add_parser("mixed", parents=[common], help="rebuild MIXED = DEV + Orca-Upstream")
    x.add_argument("--base", default="DEV")
    x.add_argument("--upstream-branch", default="Orca-Upstream")
    x.add_argument("--target", default="MIXED")

    p = sub.add_parser("workflow-policy", help="check (and with --apply enforce) the scheduled workflow policy")
    p.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    p.add_argument("--workflows-dir", type=Path, default=DEFAULT_WORKFLOWS_DIR)
    p.add_argument("--apply", action="store_true", help="disable the listed workflows on the repository")
    p.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "mirror":
            mirror(args.upstream, args.upstream_branch, resolve_origin(args), args.target, args.dry_run,
                   args.work_dir)
            return EXIT_OK
        if args.command == "mixed":
            result = mixed(resolve_origin(args), args.base, args.upstream_branch, args.target, args.dry_run,
                           args.work_dir)
            return EXIT_CONFLICT if result.status == "conflict" else EXIT_OK
        return workflow_policy(args.policy, args.workflows_dir, args.apply, args.repo)
    except SyncError as error:
        annotate("error", redact(str(error)), title="Upstream sync")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
