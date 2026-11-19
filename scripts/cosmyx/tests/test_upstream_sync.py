"""Tests of scripts/cosmyx/upstream_sync.py on temporary git repositories.

No network: "upstream" and "origin" are local bare repositories.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

COSMYX_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = COSMYX_DIR.parents[1]


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, COSMYX_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sync = load_module("upstream_sync")


class GitSandbox(unittest.TestCase):
    """Isolated git environment: no user or system config, fixed identity."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cosmyx-sync-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.summary = self.tmp / "summary.md"
        self.output = self.tmp / "output.txt"
        env = {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GITHUB_STEP_SUMMARY": str(self.summary),
            "GITHUB_OUTPUT": str(self.output),
        }
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.upstream = self.bare("upstream.git")
        self.origin = self.bare("origin.git")
        self.work = self.tmp / "work"
        self.git(["init", "-q", "-b", "main", str(self.work)])

    def git(self, args, cwd: Path | None = None) -> str:
        completed = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                                   check=False)
        if completed.returncode != 0:
            raise AssertionError(f"git {' '.join(args)}: {completed.stderr}")
        return completed.stdout.strip()

    def bare(self, name: str) -> Path:
        path = self.tmp / name
        self.git(["init", "-q", "--bare", str(path)])
        return path

    def commit(self, files: dict[str, str], message: str) -> str:
        for name, content in files.items():
            target = self.work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="\n")
        self.git(["add", "-A"], cwd=self.work)
        self.git(["commit", "-q", "-m", message], cwd=self.work)
        return self.git(["rev-parse", "HEAD"], cwd=self.work)

    def push(self, remote: Path, branch: str, rev: str = "HEAD") -> None:
        self.git(["push", "-q", "--force", str(remote), f"{rev}:refs/heads/{branch}"], cwd=self.work)

    def tip(self, remote: Path, branch: str) -> str | None:
        out = self.git(["ls-remote", str(remote), f"refs/heads/{branch}"])
        return out.split()[0] if out else None

    def outputs(self) -> dict[str, str]:
        if not self.output.exists():
            return {}
        pairs = [line.split("=", 1) for line in self.output.read_text(encoding="utf-8").splitlines() if "=" in line]
        result: dict[str, str] = {}
        for key, value in pairs:
            result[key] = value  # last write wins, like GitHub Actions
        return result

    def quiet(self, func, *args, **kwargs):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            result = func(*args, **kwargs)
        return result, buffer.getvalue()


class MirrorTests(GitSandbox):
    def setUp(self) -> None:
        super().setUp()
        self.first = self.commit({"README.md": "upstream\n"}, "upstream 1")
        self.push(self.upstream, "main")

    def run_mirror(self, dry_run: bool = False):
        return self.quiet(sync.mirror, str(self.upstream), "main", str(self.origin), "Orca-Upstream", dry_run)

    def test_creates_the_missing_branch(self) -> None:
        result, _ = self.run_mirror()
        self.assertTrue(result.changed)
        self.assertEqual(self.tip(self.origin, "Orca-Upstream"), self.first)
        self.assertEqual(self.outputs()["changed"], "true")

    def test_is_idempotent(self) -> None:
        self.run_mirror()
        result, out = self.run_mirror()
        self.assertFalse(result.changed)
        self.assertIn("already up to date", out)
        self.assertEqual(self.outputs()["changed"], "false")
        self.assertEqual(self.tip(self.origin, "Orca-Upstream"), self.first)

    def test_follows_an_upstream_history_rewrite(self) -> None:
        self.run_mirror()
        self.git(["checkout", "-q", "--orphan", "rewrite"], cwd=self.work)
        rewritten = self.commit({"README.md": "rewritten\n"}, "rewritten history")
        self.push(self.upstream, "main")
        result, _ = self.run_mirror()
        self.assertTrue(result.changed)
        self.assertEqual(self.tip(self.origin, "Orca-Upstream"), rewritten)

    def test_dry_run_pushes_nothing(self) -> None:
        result, out = self.run_mirror(dry_run=True)
        self.assertFalse(result.changed)
        self.assertIn("Dry run", out)
        self.assertIsNone(self.tip(self.origin, "Orca-Upstream"))

    def test_missing_upstream_branch_is_an_error(self) -> None:
        with self.assertRaises(sync.SyncError):
            self.quiet(sync.mirror, str(self.upstream), "nope", str(self.origin), "Orca-Upstream")


class MixedTests(GitSandbox):
    def setUp(self) -> None:
        super().setUp()
        self.root = self.commit({"shared.txt": "line\n", "README.md": "orca\n"}, "root")
        self.git(["checkout", "-q", "-b", "upstream"], cwd=self.work)
        self.up = self.commit({"upstream.txt": "new upstream file\n"}, "upstream change")
        self.push(self.origin, "Orca-Upstream")
        self.git(["checkout", "-q", "-b", "dev", self.root], cwd=self.work)
        self.dev = self.commit({"cosmyx.txt": "ours\n"}, "cosmyx change")
        self.push(self.origin, "DEV")

    def run_mixed(self, dry_run: bool = False):
        return self.quiet(sync.mixed, str(self.origin), "DEV", "Orca-Upstream", "MIXED", dry_run)

    def parents(self, sha: str) -> list[str]:
        self.git(["fetch", "-q", str(self.origin), "MIXED"], cwd=self.work)
        return self.git(["rev-list", "--parents", "-n", "1", sha], cwd=self.work).split()[1:]

    def message(self, sha: str) -> str:
        return self.git(["log", "-1", "--format=%B", sha], cwd=self.work)

    def test_clean_merge_has_two_parents_and_the_trailer(self) -> None:
        result, _ = self.run_mixed()
        self.assertEqual(result.status, "updated")
        mixed_tip = self.tip(self.origin, "MIXED")
        self.assertEqual(mixed_tip, result.commit)
        self.assertEqual(self.parents(mixed_tip), [self.dev, self.up])
        self.assertIn(f"Cosmyx-Mixed: base={self.dev} upstream={self.up}", self.message(mixed_tip))
        self.assertEqual(sync.parse_trailer(self.message(mixed_tip)), (self.dev, self.up))
        files = self.git(["ls-tree", "--name-only", mixed_tip], cwd=self.work).split()
        self.assertEqual(sorted(files), ["README.md", "cosmyx.txt", "shared.txt", "upstream.txt"])
        self.assertEqual(self.outputs()["changed"], "true")

    def test_unchanged_inputs_push_nothing(self) -> None:
        first, _ = self.run_mixed()
        self.output.unlink()
        second, out = self.run_mixed()
        self.assertEqual(second.status, "unchanged")
        self.assertIn("nothing to do", out)
        self.assertEqual(self.tip(self.origin, "MIXED"), first.commit)
        self.assertEqual(self.outputs()["changed"], "false")

    def test_a_moved_base_rebuilds_mixed(self) -> None:
        first, _ = self.run_mixed()
        dev2 = self.commit({"cosmyx.txt": "ours, again\n"}, "cosmyx change 2")
        self.push(self.origin, "DEV")
        second, _ = self.run_mixed()
        self.assertEqual(second.status, "updated")
        self.assertNotEqual(second.commit, first.commit)
        self.assertEqual(self.parents(second.commit), [dev2, self.up])

    def test_upstream_already_in_base_still_has_two_parents(self) -> None:
        self.git(["merge", "-q", "--no-edit", self.up], cwd=self.work)
        dev_merged = self.git(["rev-parse", "HEAD"], cwd=self.work)
        self.push(self.origin, "DEV")
        result, _ = self.run_mixed()
        self.assertEqual(result.status, "updated")
        self.assertEqual(self.parents(result.commit), [dev_merged, self.up])

    def test_conflict_lists_files_and_pushes_nothing(self) -> None:
        self.git(["checkout", "-q", "upstream"], cwd=self.work)
        self.commit({"shared.txt": "upstream edit\n", "other.txt": "u\n"}, "upstream edits shared")
        self.push(self.origin, "Orca-Upstream")
        self.git(["checkout", "-q", "dev"], cwd=self.work)
        self.commit({"shared.txt": "cosmyx edit\n", "other.txt": "c\n"}, "cosmyx edits shared")
        self.push(self.origin, "DEV")

        result, out = self.run_mixed()
        self.assertEqual(result.status, "conflict")
        self.assertEqual(result.conflicts, ("other.txt", "shared.txt"))
        self.assertIn("::error file=shared.txt,title=Merge conflict::", out)
        self.assertIn("::error file=other.txt,title=Merge conflict::", out)
        summary = self.summary.read_text(encoding="utf-8")
        self.assertIn("`shared.txt`", summary)
        self.assertIn("`other.txt`", summary)
        self.assertIsNone(self.tip(self.origin, "MIXED"))

    def test_conflict_exit_code_is_two(self) -> None:
        self.git(["checkout", "-q", "upstream"], cwd=self.work)
        self.commit({"shared.txt": "upstream edit\n"}, "upstream edits shared")
        self.push(self.origin, "Orca-Upstream")
        self.git(["checkout", "-q", "dev"], cwd=self.work)
        self.commit({"shared.txt": "cosmyx edit\n"}, "cosmyx edits shared")
        self.push(self.origin, "DEV")
        code, _ = self.quiet(sync.main, ["mixed", "--origin", str(self.origin)])
        self.assertEqual(code, sync.EXIT_CONFLICT)

    def test_dry_run_pushes_nothing(self) -> None:
        result, out = self.run_mixed(dry_run=True)
        self.assertEqual(result.status, "dry-run")
        self.assertIn("Dry run", out)
        self.assertIsNone(self.tip(self.origin, "MIXED"))

    def test_main_returns_zero_on_a_clean_merge(self) -> None:
        code, _ = self.quiet(sync.main, ["mixed", "--origin", str(self.origin)])
        self.assertEqual(code, sync.EXIT_OK)
        self.assertIsNotNone(self.tip(self.origin, "MIXED"))


class TrailerAndRedactTests(unittest.TestCase):
    def test_parse_trailer_takes_the_last_one(self) -> None:
        a, b, c = "a" * 40, "b" * 40, "c" * 40
        message = f"subject\n\nCosmyx-Mixed: base={a} upstream={b}\nCosmyx-Mixed: base={c} upstream={b}\n"
        self.assertEqual(sync.parse_trailer(message), (c, b))

    def test_parse_trailer_missing(self) -> None:
        self.assertIsNone(sync.parse_trailer("Merge something\n\nno trailer here\n"))

    def test_message_round_trips(self) -> None:
        base, up = "1" * 40, "2" * 40
        self.assertEqual(sync.parse_trailer(sync.mixed_message("DEV", base, "Orca-Upstream", up)), (base, up))

    def test_redact_hides_tokens(self) -> None:
        text = sync.redact("push https://x-access-token:secret123@github.com/o/r.git failed")
        self.assertNotIn("secret123", text)
        self.assertIn("https://***@github.com/o/r.git", text)

    def test_origin_falls_back_to_github_token_with_a_warning(self) -> None:
        env = {"GITHUB_REPOSITORY": "o/r", "UPSTREAM_SYNC_TOKEN": "", "GITHUB_TOKEN": "gh"}
        with mock.patch.dict(os.environ, env):
            buffer = io.StringIO()
            with redirect_stdout(buffer):
                url = sync.resolve_origin(sync.build_parser().parse_args(["mixed"]))
        self.assertEqual(url, "https://x-access-token:gh@github.com/o/r.git")
        self.assertIn("::warning", buffer.getvalue())

    def test_origin_prefers_the_sync_token(self) -> None:
        env = {"GITHUB_REPOSITORY": "o/r", "UPSTREAM_SYNC_TOKEN": "pat", "GITHUB_TOKEN": "gh"}
        with mock.patch.dict(os.environ, env):
            url = sync.resolve_origin(sync.build_parser().parse_args(["mirror"]))
        self.assertEqual(url, "https://x-access-token:pat@github.com/o/r.git")


def completed(code: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(["gh"], code, stdout, stderr)


class FakeGh:
    """Answers gh api calls from a {workflow: state} table; None means 404."""

    def __init__(self, states: dict[str, str | None], disable_errors: dict[str, str] | None = None) -> None:
        self.states = states
        self.disable_errors = disable_errors or {}
        self.calls: list[list[str]] = []

    def __call__(self, args):
        args = list(args)
        self.calls.append(args)
        endpoint = next(a for a in args if a.startswith("repos/"))
        name = endpoint.split("/actions/workflows/", 1)[1].split("/", 1)[0]
        if "PUT" in args:
            if name in self.disable_errors:
                return completed(1, stderr=self.disable_errors[name])
            self.states[name] = "disabled_manually"
            return completed(0)
        state = self.states.get(name)
        if state is None:
            return completed(1, stderr="gh: Not Found (HTTP 404)")
        return completed(0, stdout=state + "\n")


class WorkflowPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cosmyx-policy-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.workflows = self.tmp / "workflows"
        self.workflows.mkdir()
        patcher = mock.patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": "", "GITHUB_OUTPUT": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def workflow(self, name: str, text: str) -> None:
        (self.workflows / name).write_text(text, encoding="utf-8", newline="\n")

    def policy(self, **data) -> Path:
        path = self.tmp / "policy.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def run_policy(self, policy: Path, apply: bool = False, runner=None) -> tuple[int, str]:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = sync.workflow_policy(policy, self.workflows, apply, "o/r", runner or FakeGh({}))
        return code, buffer.getvalue()

    def test_schedule_detection(self) -> None:
        self.assertTrue(sync.is_scheduled("on:\n  schedule:\n    - cron: '0 0 * * *'\n"))
        self.assertTrue(sync.is_scheduled("on: [push, schedule]\n"))
        self.assertTrue(sync.is_scheduled("'on':\n  \"schedule\":\n"))
        self.assertFalse(sync.is_scheduled("on:\n  # schedule:\n  #   - cron: 0 0 * * 1\n  workflow_dispatch:\n"))
        self.assertFalse(sync.is_scheduled("on:\n  push:\n    paths: ['x#schedule:']\n"))

    def test_unknown_scheduled_workflow_fails(self) -> None:
        self.workflow("known.yml", "on:\n  schedule:\n    - cron: '1 1 * * *'\n")
        self.workflow("newbot.yml", "on:\n  schedule:\n    - cron: '2 2 * * *'\n")
        code, out = self.run_policy(self.policy(allow_scheduled=["known.yml"], disable=[]))
        self.assertEqual(code, sync.EXIT_ERROR)
        self.assertIn("::error title=Workflow policy::newbot.yml", out)

    def test_listed_workflows_pass_and_unscheduled_are_ignored(self) -> None:
        self.workflow("allowed.yml", "on:\n  schedule:\n    - cron: '1 1 * * *'\n")
        self.workflow("bot.yaml", "on:\n  schedule:\n    - cron: '1 1 * * *'\n")
        self.workflow("ci.yml", "on:\n  push:\n")
        self.workflow("notes.txt", "schedule:\n")
        code, _ = self.run_policy(self.policy(allow_scheduled=["allowed.yml"], disable=["bot.yaml"]))
        self.assertEqual(code, sync.EXIT_OK)

    def test_cosmyx_owned_scheduled_workflow_needs_no_entry(self) -> None:
        self.workflow("cosmyx-foo.yml", "on:\n  schedule:\n    - cron: '3 3 * * 1'\n")
        self.workflow("upstream-new.yml", "on:\n  schedule:\n    - cron: '4 4 * * *'\n")
        code, out = self.run_policy(self.policy(allow_scheduled=[], disable=[]))
        self.assertEqual(code, sync.EXIT_ERROR)
        self.assertIn("::error title=Workflow policy::upstream-new.yml", out)
        self.assertNotIn("cosmyx-foo.yml has a schedule trigger", out)
        (self.workflows / "upstream-new.yml").unlink()
        code, out = self.run_policy(self.policy(allow_scheduled=[], disable=[]))
        self.assertEqual(code, sync.EXIT_OK, out)

    def test_owned_glob_is_configurable_and_case_sensitive(self) -> None:
        self.workflow("Cosmyx-foo.yml", "on:\n  schedule:\n    - cron: '3 3 * * 1'\n")
        code, _ = self.run_policy(self.policy())
        self.assertEqual(code, sync.EXIT_ERROR)
        code, _ = self.run_policy(self.policy(cosmyx_owned_glob="Cosmyx-*.yml"))
        self.assertEqual(code, sync.EXIT_OK)
        # An empty glob turns the exemption off.
        self.workflow("cosmyx-bar.yml", "on:\n  schedule:\n    - cron: '3 3 * * 1'\n")
        code, _ = self.run_policy(self.policy(cosmyx_owned_glob=""))
        self.assertEqual(code, sync.EXIT_ERROR)

    def test_cosmyx_owned_workflow_is_never_disabled(self) -> None:
        code, out = self.run_policy(self.policy(disable=["cosmyx-foo.yml"]))
        self.assertEqual(code, sync.EXIT_ERROR)
        self.assertIn("cosmyx-foo.yml is Cosmyx-owned", out)
        fake = FakeGh({"cosmyx-foo.yml": "active"})
        lines = sync.apply_policy(sync.Policy(["cosmyx-foo.yml"], [], []), "o/r", fake)
        self.assertEqual(lines, ["cosmyx-foo.yml: Cosmyx-owned, never disabled"])
        self.assertEqual(fake.calls, [])

    def test_both_lists_or_must_stay_enabled_conflicts_fail(self) -> None:
        code, _ = self.run_policy(self.policy(allow_scheduled=["a.yml"], disable=["a.yml"]))
        self.assertEqual(code, sync.EXIT_ERROR)
        code, _ = self.run_policy(self.policy(disable=["build_all.yml"], must_stay_enabled=["build_all.yml"]))
        self.assertEqual(code, sync.EXIT_ERROR)

    def test_apply_is_idempotent_and_tolerant(self) -> None:
        fake = FakeGh(
            {"stale.yml": "active", "assign.yml": "active", "approve.yml": "disabled_manually", "build_all.yml": "active"},
            disable_errors={"assign.yml": "gh: Workflow is not active (HTTP 403)"},
        )
        policy = sync.Policy(disable=["stale.yml", "assign.yml", "approve.yml", "dupes.yml"], allow_scheduled=[],
                             must_stay_enabled=["build_all.yml"])
        lines = sync.apply_policy(policy, "o/r", fake)
        self.assertEqual(lines, [
            "stale.yml: disabled",
            "assign.yml: not active",
            "approve.yml: already disabled_manually",
            "dupes.yml: not registered on o/r yet, retried next run",
            "build_all.yml: must stay enabled (active)",
        ])
        puts = [c for c in fake.calls if "PUT" in c]
        self.assertEqual(len(puts), 2)
        # Second run: nothing left to disable.
        fake.calls.clear()
        again = sync.apply_policy(policy, "o/r", fake)
        self.assertEqual(again[0], "stale.yml: already disabled_manually")
        # Only the inactive one is retried, and it is still tolerated.
        self.assertEqual([c for c in fake.calls if "PUT" in c],
                         [["api", "-X", "PUT", "repos/o/r/actions/workflows/assign.yml/disable"]])
        self.assertEqual(again[1], "assign.yml: not active")

    def test_apply_raises_on_unexpected_errors(self) -> None:
        fake = FakeGh({"stale.yml": "active"}, disable_errors={"stale.yml": "gh: Resource not accessible (HTTP 403)"})
        with self.assertRaises(sync.SyncError):
            sync.apply_policy(sync.Policy(["stale.yml"], [], []), "o/r", fake)

    def test_repository_policy_covers_every_scheduled_workflow(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = sync.workflow_policy(sync.DEFAULT_POLICY, sync.DEFAULT_WORKFLOWS_DIR, False, None)
        self.assertEqual(code, sync.EXIT_OK, buffer.getvalue())

    def test_repository_policy_keeps_build_all_enabled(self) -> None:
        policy = sync.load_policy(sync.DEFAULT_POLICY)
        self.assertIn("build_all.yml", policy.must_stay_enabled)
        self.assertNotIn("build_all.yml", policy.disable)
        self.assertTrue(policy.is_owned("cosmyx-upstream-sync.yml"))
        self.assertIn("cosmyx-upstream-sync.yml", policy.must_stay_enabled)


class WorkflowFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (REPO_ROOT / ".github" / "workflows" / "cosmyx-upstream-sync.yml").read_text(encoding="utf-8")

    def test_is_scheduled_and_dispatchable(self) -> None:
        self.assertTrue(sync.is_scheduled(self.text))
        self.assertIn("cron: '23 */6 * * *'", self.text)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("dry_run:", self.text)

    def test_never_cancels_a_running_sync(self) -> None:
        self.assertIn("group: cosmyx-upstream-sync", self.text)
        self.assertIn("cancel-in-progress: false", self.text)

    def test_dispatches_build_all_on_mixed(self) -> None:
        self.assertIn("gh workflow run build_all.yml --repo \"$GITHUB_REPOSITORY\" --ref MIXED", self.text)
        self.assertIn("actions: write", self.text)
        self.assertIn("secrets.UPSTREAM_SYNC_TOKEN", self.text)

    def test_is_ascii_and_lf(self) -> None:
        raw = (REPO_ROOT / ".github" / "workflows" / "cosmyx-upstream-sync.yml").read_bytes()
        self.assertNotIn(b"\r", raw)
        raw.decode("ascii")


if __name__ == "__main__":
    unittest.main()
