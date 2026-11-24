"""Tests of scripts/cosmyx/integrate/cli.py on throwaway git repositories.

No network: "origin" is a local bare repository; the branding engine is a
fake hook that renders the review table from the manifest.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

COSMYX_DIR = Path(__file__).resolve().parents[1]
if str(COSMYX_DIR) not in sys.path:
    sys.path.insert(0, str(COSMYX_DIR))

from integrate import cli, resolve  # noqa: E402

CHANGELOG = """# Changelog

## 2026-11

### repo

<!-- cosmyx-slot: T0 -->
- Foundation.

### GUI

<!-- cosmyx-slot: T5 -->
"""

SLOTS_PY = '''SLOTS_BY_AREA = {
    "repo": ["T0"],
    "GUI": ["T5"],
}


def unrelated():
    return 1
'''

SLOTS_MD = """# 0003. Changelog slot markers

- Markers in place, by area:
  - `repo`: T0.
  - `GUI`: T5.
- Decision numbers are reserved.
"""

MANIFEST = "cosmyx-src/branding/manifest/web.json"
TABLE = "wiki/cosmyx/branding-assets/web.md"


def manifest_text(rows: list[tuple[str, str]]) -> str:
    return json.dumps({"schema": 1, "rows": [{"path": path, "status": status} for path, status in rows]}, indent=2) + "\n"


def fake_brand_engine(worktree: Path) -> None:
    """Render the review table from the manifest, like `brand-table` would."""
    rows = json.loads((worktree / MANIFEST).read_text(encoding="utf-8"))["rows"]
    lines = ["| Path | Status |"] + [f"| {row['path']} | {row['status']} |" for row in sorted(rows, key=lambda r: r["path"])]
    lines.append(f"{sum(row['status'] == 'validated' for row in rows)} validated of {len(rows)} rows.")
    (worktree / TABLE).parent.mkdir(parents=True, exist_ok=True)
    (worktree / TABLE).write_bytes(("\n".join(lines) + "\n").encode("utf-8"))


class Sandbox(unittest.TestCase):
    """Isolated git environment: no user or system config, fixed identity."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cosmyx-integrate-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        env = {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.origin = self.tmp / "origin.git"
        self.work = self.tmp / "work"
        self.git(["init", "-q", "--bare", "-b", "DEV", str(self.origin)], cwd=self.tmp)
        self.git(["init", "-q", "-b", "DEV", str(self.work)], cwd=self.tmp)
        self.git(["remote", "add", "origin", str(self.origin)])
        self.base = self.commit({
            "CHANGELOG.md": CHANGELOG,
            resolve.SLOTS_PY: SLOTS_PY,
            resolve.SLOTS_MD: SLOTS_MD,
            "src/app.txt": "one\ntwo\nthree\n",
            MANIFEST: manifest_text([("a.svg", "validated")] + [(f"m{i}.svg", "to-validate") for i in range(8)]
                                    + [("z.svg", "validated")]),
        }, "base", hook=True)
        self.push("DEV")
        self.rows: list[dict] = []

    # helpers

    def git(self, args, cwd: Path | None = None) -> str:
        completed = subprocess.run(["git", *args], cwd=str(cwd or self.work), capture_output=True, text=True,
                                   check=False)
        if completed.returncode != 0:
            raise AssertionError(f"git {' '.join(args)}: {completed.stderr}")
        return completed.stdout.strip()

    def commit(self, files: dict[str, str], message: str, hook: bool = False) -> str:
        for name, content in files.items():
            target = self.work / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.encode("utf-8"))
        if hook:
            fake_brand_engine(self.work)
        self.git(["add", "-A"])
        self.git(["commit", "-q", "-m", message])
        return self.git(["rev-parse", "HEAD"])

    def push(self, branch: str) -> None:
        self.git(["push", "-q", "--force", "origin", f"HEAD:refs/heads/{branch}"])

    def branch(self, name: str, parent: str, files: dict[str, str], from_ref: str | None = None,
               hook: bool = False) -> str:
        self.git(["checkout", "-q", "-B", name, from_ref or self.base])
        sha = self.commit(files, f"{name} change", hook=hook)
        self.push(name)
        self.rows.append({"name": name, "parent": parent})
        self.git(["checkout", "-q", "DEV"])
        return sha

    def data(self, extra: list[dict] | None = None) -> str:
        path = self.tmp / "branches.json"
        rows = [{"name": "chore/foundation", "parent": "DEV"}] + self.rows + (extra or [])
        path.write_text(json.dumps({"remote": "origin", "base": "DEV", "foundation": "chore/foundation",
                                    "branches": rows}), encoding="utf-8")
        return str(path)

    def foundation(self) -> str:
        self.git(["checkout", "-q", "-B", "chore/foundation", self.base])
        sha = self.commit({"README.md": "foundation\n"}, "foundation")
        self.push("chore/foundation")
        self.git(["checkout", "-q", "DEV"])
        self.base = sha
        return sha

    def changelog_with(self, *blocks: tuple[str, str]) -> str:
        text = CHANGELOG
        for marker, line in blocks:
            text = text.replace("- Foundation.\n", f"- Foundation.\n\n<!-- cosmyx-slot: {marker} -->\n- {line}\n", 1)
        return text

    def run_cli(self, argv: list[str], **kwargs) -> tuple[int, str]:
        args = cli.parser().parse_args(argv + ["--repo-root", str(self.work)])
        out = io.StringIO()
        func = cli.integrate if args.command == "integrate" else cli.rebase_check
        kwargs.setdefault("brand_hook", fake_brand_engine)
        return func(args, out=out, **kwargs), out.getvalue()

    def integration_file(self, path: str) -> str:
        return self.git(["show", f"ci/cosmyx-integration:{path}"])


class IntegrateTests(Sandbox):
    def setUp(self) -> None:
        super().setUp()
        self.foundation()

    def slot_branch(self, name: str, marker: str, area_line: str) -> None:
        self.branch(name, "chore/foundation", {
            "CHANGELOG.md": self.changelog_with((marker, f"{name} line.")),
            resolve.SLOTS_PY: SLOTS_PY.replace('"repo": ["T0"]', f'"repo": ["T0", "{marker}"]'),
            resolve.SLOTS_MD: SLOTS_MD.replace("`repo`: T0.", f"`repo`: T0, {marker}."),
            f"src/{name.replace('/', '-')}.txt": "x\n",
        }, from_ref=self.base)

    def test_slot_unions_resolved_inside_the_merge(self) -> None:
        self.slot_branch("feat/a", "T17", "")
        self.slot_branch("feat/b", "T20", "")
        code, out = self.run_cli(["integrate", "--no-fetch", "--data", self.data()])
        self.assertEqual(code, 0, out)
        self.assertIn("auto-resolved", out)
        changelog = self.integration_file("CHANGELOG.md")
        self.assertEqual(list(resolve.marker_order(changelog)), ["T0", "T17", "T20", "T5"])
        self.assertIn('"repo": ["T0", "T17", "T20"],', self.integration_file(resolve.SLOTS_PY))
        self.assertIn("`repo`: T0, T17, T20.", self.integration_file(resolve.SLOTS_MD))
        # Each feature merge is a --no-ff merge of origin/<branch>.
        parents = self.git(["log", "--first-parent", "--format=%P", "ci/cosmyx-integration"]).splitlines()
        self.assertEqual([len(line.split()) for line in parents[:3]], [2, 2, 2])
        # Not pushed by default.
        self.assertEqual(self.git(["ls-remote", str(self.origin), "refs/heads/ci/cosmyx-integration"]), "")

    def test_manifest_tables_take_one_side_then_regenerate(self) -> None:
        rows = [("a.svg", "validated")] + [(f"m{i}.svg", "to-validate") for i in range(8)] + [("z.svg", "validated")]
        first = [("0.svg", "validated")] + rows
        second = rows + [("zz.svg", "validated")]
        self.branch("feat/brand1", "chore/foundation", {MANIFEST: manifest_text(first)}, from_ref=self.base, hook=True)
        self.branch("feat/brand2", "chore/foundation", {MANIFEST: manifest_text(second)}, from_ref=self.base, hook=True)
        calls = []

        def hook(worktree: Path) -> None:
            calls.append(worktree)
            fake_brand_engine(worktree)

        code, out = self.run_cli(["integrate", "--no-fetch", "--data", self.data()], brand_hook=hook)
        self.assertEqual(code, 0, out)
        self.assertEqual(len(calls), 1)
        self.assertIn("brand-sync", out)
        table = self.integration_file(TABLE)
        for path in ("0.svg", "zz.svg", "a.svg"):
            self.assertIn(f"| {path} | validated |", table)

    def test_manifest_conflict_losing_validated_rows_stops(self) -> None:
        self.branch("feat/brand1", "chore/foundation", {MANIFEST: manifest_text([("a.svg", "validated")])},
                    from_ref=self.base, hook=True)
        self.branch("feat/brand2", "chore/foundation", {MANIFEST: manifest_text([("b.svg", "validated")])},
                    from_ref=self.base, hook=True)
        code, out = self.run_cli(["integrate", "--no-fetch", "--data", self.data()])
        self.assertEqual(code, 1, out)
        self.assertIn("validated rows lost", out)

    def test_unknown_conflict_aborts_and_reports(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/app.txt": "one\nTWO-A\nthree\n"}, from_ref=self.base)
        self.branch("feat/b", "chore/foundation", {"src/app.txt": "one\nTWO-B\nthree\n"}, from_ref=self.base)
        self.branch("feat/c", "chore/foundation", {"src/c.txt": "c\n"}, from_ref=self.base)
        code, out = self.run_cli(["integrate", "--no-fetch", "--data", self.data()])
        self.assertEqual(code, 1)
        self.assertIn("UNKNOWN CONFLICT in origin/feat/b", out)
        self.assertIn("src/app.txt", out)
        self.assertIn("TWO-A", out)
        self.assertNotIn("feat/c ", out.split("UNKNOWN")[0])
        worktree = self.work / ".worktrees" / "integration"
        self.assertEqual(self.git(["status", "--porcelain"], cwd=worktree), "")
        self.assertIsNone(cli.Git(worktree).sha("MERGE_HEAD"))
        self.assertEqual(self.integration_file("src/app.txt"), "one\nTWO-A\nthree")

    def test_rerere_replays_a_resolution_trained_from_the_old_integration(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/app.txt": "one\nTWO-A\nthree\n"}, from_ref=self.base)
        self.branch("feat/b", "chore/foundation", {"src/app.txt": "one\nTWO-B\nthree\n"}, from_ref=self.base)
        # A hand-made integration that resolved the conflict, already pushed.
        self.git(["checkout", "-q", "-B", "old", self.base])
        self.git(["merge", "-q", "--no-ff", "--no-edit", "origin/chore/foundation"])
        self.git(["merge", "-q", "--no-ff", "--no-edit", "origin/feat/a"])
        subprocess.run(["git", "merge", "--no-ff", "origin/feat/b"], cwd=self.work, capture_output=True, check=False)
        (self.work / "src/app.txt").write_bytes(b"one\nTWO-A\nTWO-B\nthree\n")
        self.git(["add", "src/app.txt"])
        self.git(["commit", "-q", "--no-edit"])
        self.push("ci/cosmyx-integration")
        self.git(["fetch", "-q", "origin"])
        self.git(["checkout", "-q", "DEV"])
        code, out = self.run_cli(["integrate", "--no-fetch", "--data", self.data()])
        self.assertEqual(code, 0, out)
        self.assertIn("rerere trained on 1", out)
        self.assertIn("auto-resolved: rerere", out)
        self.assertEqual(self.integration_file("src/app.txt"), "one\nTWO-A\nTWO-B\nthree")

    def test_push_uses_a_lease_and_build_calls_gh(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.push("ci/cosmyx-integration")  # an old remote tip (DEV)
        self.git(["fetch", "-q", "origin"])
        calls = []

        def gh(command):
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")

        code, out = self.run_cli(["integrate", "--no-fetch", "--no-train", "--data", self.data(), "--push", "--build",
                                  "--repo", "Owner/Repo"], gh=gh)
        self.assertEqual(code, 0, out)
        local = self.git(["rev-parse", "ci/cosmyx-integration"])
        self.assertEqual(self.git(["ls-remote", str(self.origin), "refs/heads/ci/cosmyx-integration"]).split()[0], local)
        self.assertEqual(calls, [["workflow", "run", "build_all.yml", "--ref", "ci/cosmyx-integration",
                                  "--repo", "Owner/Repo"]])

    def test_push_refuses_when_the_remote_moved(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.push("ci/cosmyx-integration")
        self.git(["fetch", "-q", "origin"])
        # Someone else pushes after our fetch.
        self.git(["checkout", "-q", "-B", "other", self.base])
        self.commit({"src/other.txt": "o\n"}, "other")
        # Pushed by URL, so our remote-tracking ref stays at the old tip.
        self.git(["push", "-q", "--force", str(self.origin), "HEAD:refs/heads/ci/cosmyx-integration"])
        self.git(["checkout", "-q", "DEV"])
        with self.assertRaises(cli.SetupError):
            self.run_cli(["integrate", "--no-fetch", "--no-train", "--data", self.data(), "--push"])

    def test_build_needs_push(self) -> None:
        with self.assertRaises(cli.SetupError):
            self.run_cli(["integrate", "--no-fetch", "--data", self.data(), "--build"])

    def test_dirty_worktree_is_refused(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.assertEqual(self.run_cli(["integrate", "--no-fetch", "--data", self.data()])[0], 0)
        (self.work / ".worktrees" / "integration" / "src" / "a.txt").write_bytes(b"dirty\n")
        with self.assertRaises(cli.SetupError):
            self.run_cli(["integrate", "--no-fetch", "--data", self.data()])

    def test_missing_branch_changes_nothing(self) -> None:
        with self.assertRaises(cli.SetupError):
            self.run_cli(["integrate", "--no-fetch", "--data", self.data([{"name": "feat/gone", "parent": "DEV"}])])
        self.assertFalse((self.work / ".worktrees").exists())


class RebaseCheckTests(Sandbox):
    def setUp(self) -> None:
        super().setUp()
        self.foundation()
        # Upstream release: DEV's base plus one upstream change, tagged.
        self.git(["checkout", "-q", "-B", "upstream", self.git(["rev-parse", "origin/DEV"])])
        self.commit({"src/app.txt": "one\ntwo upstream\nthree\n", "src/up.txt": "up\n"}, "upstream release")
        self.git(["tag", "upstream/v1"])
        self.git(["checkout", "-q", "DEV"])

    def worktrees(self) -> list[str]:
        return [line for line in self.git(["worktree", "list", "--porcelain"]).splitlines() if line.startswith("worktree ")]

    def test_table_and_cleanup(self) -> None:
        self.branch("feat/a", "DEV", {"CHANGELOG.md": self.changelog_with(("T17", "a.")),
                                      resolve.SLOTS_PY: SLOTS_PY.replace('["T0"]', '["T0", "T17"]')},
                    from_ref=self.base)
        child_base = self.git(["rev-parse", "origin/feat/a"])
        self.branch("feat/a-child", "feat/a", {"src/child.txt": "c\n"}, from_ref=child_base)
        self.branch("feat/clash", "DEV", {"src/app.txt": "one\ntwo mine\nthree\n"}, from_ref=self.base)
        self.branch("feat/b", "DEV", {"CHANGELOG.md": self.changelog_with(("T20", "b.")),
                                      resolve.SLOTS_PY: SLOTS_PY.replace('["T0"]', '["T0", "T20"]')},
                    from_ref=self.base)
        refs_before = self.git(["for-each-ref"])
        code, out = self.run_cli(["rebase-check", "v1", "--no-fetch", "--data", self.data()])
        self.assertEqual(code, 1, out)
        lines = {line.split("|")[1].strip(): line for line in out.splitlines() if line.startswith("| ")}
        self.assertIn("clean", lines["chore/foundation"])
        self.assertIn("clean", lines["feat/a"])
        self.assertIn("1 commits", lines["feat/a-child"])
        self.assertIn("CONFLICT", lines["feat/clash"])
        self.assertIn("src/app.txt", lines["feat/clash"])
        self.assertIn("clean", lines["feat/b"])
        self.assertEqual(self.git(["for-each-ref"]), refs_before)
        self.assertEqual(len(self.worktrees()), 1)

    def test_stacked_slot_conflict_is_auto_resolved(self) -> None:
        self.branch("feat/a", "DEV", {"CHANGELOG.md": self.changelog_with(("T17", "a.")),
                                      resolve.SLOTS_MD: SLOTS_MD.replace("`repo`: T0.", "`repo`: T0, T17.")},
                    from_ref=self.base)
        # A sibling stacked on feat/a that was written against an older feat/a.
        self.git(["checkout", "-q", "-B", "feat/a2", self.base])
        self.commit({"CHANGELOG.md": self.changelog_with(("T17", "a.")),
                     resolve.SLOTS_MD: SLOTS_MD.replace("`repo`: T0.", "`repo`: T0, T17.")}, "old a")
        self.commit({"CHANGELOG.md": self.changelog_with(("T17", "a."), ("T21", "a2.")),
                     resolve.SLOTS_MD: SLOTS_MD.replace("`repo`: T0.", "`repo`: T0, T17, T21.")}, "a2")
        self.push("feat/a2")
        self.git(["checkout", "-q", "DEV"])
        self.rows.append({"name": "feat/a2", "parent": "DEV"})
        code, out = self.run_cli(["rebase-check", "v1", "--no-fetch", "--data", self.data()])
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.worktrees()), 1)

    def test_missing_tag_without_fetch_fails_cleanly(self) -> None:
        with self.assertRaises(cli.SetupError):
            self.run_cli(["rebase-check", "v9", "--no-fetch", "--data", self.data()])
        self.assertEqual(len(self.worktrees()), 1)

    def test_worktree_removed_on_error(self) -> None:
        self.branch("feat/a", "DEV", {"src/a.txt": "a\n"}, from_ref=self.base)

        def boom(*_args, **_kwargs):
            raise RuntimeError("boom")

        with mock.patch.object(cli, "replay", boom), self.assertRaises(RuntimeError):
            self.run_cli(["rebase-check", "v1", "--no-fetch", "--data", self.data()])
        self.assertEqual(len(self.worktrees()), 1)


class BranchListTests(unittest.TestCase):
    def test_shipped_list_is_ordered(self) -> None:
        data, entries = cli.load_branches()
        self.assertEqual(entries[0].name, data["foundation"])
        self.assertTrue(entries[-1].integration_only)
        self.assertEqual(len({entry.name for entry in entries}), len(entries))

    def test_child_before_parent_is_refused(self) -> None:
        data = {"base": "DEV", "foundation": "f"}
        with self.assertRaises(cli.SetupError):
            cli.check_branches(data, [cli.Entry("f", "DEV"), cli.Entry("c", "p"), cli.Entry("p", "DEV")])
        with self.assertRaises(cli.SetupError):
            cli.check_branches(data, [cli.Entry("f", "DEV"), cli.Entry("f", "DEV")])


if __name__ == "__main__":
    unittest.main()
