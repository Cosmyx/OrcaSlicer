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
        # Resolved once so every path is in its canonical long form: Windows hands out an 8.3 short temp
        # path (RUNNER~1) while git prints the long one, and macOS links /var to /private/var.
        self.tmp = Path(tempfile.mkdtemp(prefix="cosmyx-integrate-test-")).resolve()
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
        rows = [{"bundle": 1, **row} for row in rows]
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

    def remote_sha(self, branch: str) -> str | None:
        line = self.git(["ls-remote", str(self.origin), f"refs/heads/{branch}"])
        return line.split()[0] if line else None

    def fake_gh(self, open_prs: list[dict], repo_labels: tuple[str, ...] = ()):
        """A gh stand-in: `pr list` returns open_prs, `label list` repo_labels; records each call with the
        remote cosmyx-ci/DEV at that moment."""
        calls = []

        def gh(command):
            calls.append((command, self.remote_sha("cosmyx-ci/DEV")))
            if command[:2] == ["pr", "list"]:
                return subprocess.CompletedProcess(command, 0, json.dumps(open_prs), "")
            if command[:2] == ["label", "list"]:
                return subprocess.CompletedProcess(command, 0, json.dumps([{"name": n} for n in repo_labels]), "")
            if command[:2] == ["pr", "create"]:
                return subprocess.CompletedProcess(command, 0, "https://github.com/Owner/Repo/pull/7\n", "")
            return subprocess.CompletedProcess(command, 0, "", "")

        return gh, calls

    def test_drift_is_not_checked_on_the_list_base(self) -> None:
        tail = "".join(f"added {number}\n" for number in range(50))
        self.branch("feat/big", "chore/foundation", {"src/app.txt": "one\ntwo\nthree\n" + tail}, from_ref=self.base)
        code, out = self.run_cli(["integrate", "--no-fetch", "--strict-drift", "--data", self.data()])
        self.assertEqual(code, 0, out)
        self.assertNotIn("DRIFT", out)

    def test_push_also_pushes_the_ci_base_at_the_base_commit(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.push("ci/cosmyx-integration")  # an old remote tip (DEV)
        self.git(["fetch", "-q", "origin"])
        code, out = self.run_cli(["integrate", "--no-fetch", "--no-train", "--data", self.data(), "--push"])
        self.assertEqual(code, 0, out)
        self.assertEqual(self.remote_sha("ci/cosmyx-integration"), self.git(["rev-parse", "ci/cosmyx-integration"]))
        self.assertEqual(self.remote_sha("cosmyx-ci/DEV"), self.git(["rev-parse", "origin/DEV"]))

    def test_tag_base_gives_its_own_ci_base(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.git(["tag", "v1", "origin/DEV"])
        code, out = self.run_cli(["integrate", "v1", "--no-fetch", "--no-train", "--data", self.data(), "--push"])
        self.assertEqual(code, 0, out)
        self.assertEqual(self.remote_sha("cosmyx-ci/v1"), self.git(["rev-parse", "v1^{commit}"]))
        self.assertIsNone(self.remote_sha("cosmyx-ci/DEV"))
        # A base other than the list's gets its own branch and worktree.
        self.assertEqual(self.remote_sha("integration/v1"), self.git(["rev-parse", "integration/v1"]))
        self.assertIsNone(self.remote_sha("ci/cosmyx-integration"))
        self.assertTrue((self.work / ".worktrees" / "integration-v1").is_dir())
        self.assertFalse((self.work / ".worktrees" / "integration").exists())

    def test_integrations_of_two_bases_coexist(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.git(["tag", "v1", "origin/DEV"])
        code, out = self.run_cli(["integrate", "--no-fetch", "--no-train", "--data", self.data(), "--push"])
        self.assertEqual(code, 0, out)
        dev_tip = self.remote_sha("ci/cosmyx-integration")
        self.git(["fetch", "-q", "origin"])
        code, out = self.run_cli(["integrate", "v1", "--no-fetch", "--no-train", "--data", self.data(), "--push"])
        self.assertEqual(code, 0, out)
        self.assertEqual(self.remote_sha("ci/cosmyx-integration"), dev_tip)
        self.assertEqual(self.git(["rev-parse", "ci/cosmyx-integration"]), dev_tip)
        self.assertEqual(self.remote_sha("integration/v1"), self.git(["rev-parse", "integration/v1"]))
        self.assertEqual(self.remote_sha("cosmyx-ci/DEV"), self.git(["rev-parse", "origin/DEV"]))

    def test_build_on_another_base_leaves_other_integration_pull_requests_alone(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.git(["tag", "v1", "origin/DEV"])
        gh, calls = self.fake_gh([
            {"number": 4, "url": "https://github.com/Owner/Repo/pull/4", "baseRefName": "cosmyx-ci/DEV",
             "headRefName": "ci/cosmyx-integration"},
            {"number": 5, "url": "https://github.com/Owner/Repo/pull/5", "baseRefName": "cosmyx-ci/v0",
             "headRefName": "integration/v1"},
        ])
        code, out = self.run_cli(["integrate", "v1", "--no-fetch", "--no-train", "--data", self.data(), "--push",
                                  "--build"], gh=gh)
        self.assertEqual(code, 0, out)
        self.assertEqual([command[:3] for command, _ in calls],
                         [["pr", "list", "--head"], ["pr", "close", "5"], ["pr", "create", "--draft"]])
        self.assertEqual(calls[0][0][calls[0][0].index("--head") + 1], "integration/v1")
        create = calls[2][0]
        self.assertEqual(create[create.index("--head") + 1], "integration/v1")
        self.assertEqual(create[create.index("--base") + 1], "cosmyx-ci/v1")
        self.assertIn("--branch integration/v1", out)

    def test_base_without_a_branch_name_is_refused_before_any_work(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        with self.assertRaises(cli.SetupError):
            self.run_cli(["integrate", "origin/DEV~0", "--no-fetch", "--data", self.data(), "--push"])
        self.assertFalse((self.work / ".worktrees").exists())

    def test_ci_base_lease_refuses_and_pushes_nothing(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        # Someone pushes cosmyx-ci/DEV after our fetch, from their own clone, so
        # our remote-tracking refs do not know it.
        other = self.tmp / "other"
        self.git(["clone", "-q", str(self.origin), str(other)], cwd=self.tmp)
        self.git(["push", "-q", "origin", "origin/chore/foundation:refs/heads/cosmyx-ci/DEV"], cwd=other)
        with self.assertRaises(cli.SetupError):
            self.run_cli(["integrate", "--no-fetch", "--no-train", "--data", self.data(), "--push"])
        self.assertIsNone(self.remote_sha("ci/cosmyx-integration"))
        self.assertEqual(self.remote_sha("cosmyx-ci/DEV"), self.base)

    def test_build_creates_a_draft_pull_request_after_the_push(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        gh, calls = self.fake_gh([])
        code, out = self.run_cli(["integrate", "--no-fetch", "--no-train", "--data", self.data(), "--push", "--build",
                                  "--repo", "Owner/Repo"], gh=gh)
        self.assertEqual(code, 0, out)
        self.assertEqual([command[:2] for command, _ in calls], [["pr", "list"], ["pr", "create"]])
        listed, _ = calls[0]
        self.assertEqual(listed[listed.index("--head") + 1], "ci/cosmyx-integration")
        self.assertEqual(listed[-2:], ["--repo", "Owner/Repo"])
        create, ci_at_create = calls[1]
        self.assertEqual(ci_at_create, self.git(["rev-parse", "origin/DEV"]))
        self.assertIn("--draft", create)
        self.assertEqual(create[create.index("--head") + 1], "ci/cosmyx-integration")
        self.assertEqual(create[create.index("--base") + 1], "cosmyx-ci/DEV")
        self.assertEqual(create[create.index("--title") + 1], "ci: integration build on DEV (never merge)")
        self.assertIn("Never merge", create[create.index("--body") + 1])
        self.assertEqual(create[-2:], ["--repo", "Owner/Repo"])
        self.assertIn("https://github.com/Owner/Repo/pull/7", out)
        self.assertIn("gh run list --workflow cosmyx-dev-build.yml --branch ci/cosmyx-integration --repo Owner/Repo",
                      out)
        # No --os: no label is read, created or set (the workflow's default set).
        self.assertNotIn("--label", create)

    def test_os_labels_a_new_pull_request_at_creation_and_creates_missing_labels(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        gh, calls = self.fake_gh([], repo_labels=("build:linux",))
        code, out = self.run_cli(["integrate", "--no-fetch", "--no-train", "--data", self.data(), "--push", "--build",
                                  "--os", "macos-x86_64, linux", "--repo", "Owner/Repo"], gh=gh)
        self.assertEqual(code, 0, out)
        self.assertEqual([command[:3] for command, _ in calls],
                         [["pr", "list", "--head"], ["label", "list", "--search"],
                          ["label", "create", "build:macos-x86_64"], ["pr", "create", "--draft"]])
        self.assertEqual(calls[2][0][-2:], ["--repo", "Owner/Repo"])
        create = calls[3][0]
        labels = [create[i + 1] for i, arg in enumerate(create) if arg == "--label"]
        self.assertEqual(labels, ["build:linux", "build:macos-x86_64"])
        self.assertIn("Created label build:macos-x86_64.", out)

    def test_os_syncs_a_reused_pull_request_labels_before_the_push(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        gh, calls = self.fake_gh([
            {"number": 6, "url": "https://github.com/Owner/Repo/pull/6", "baseRefName": "cosmyx-ci/DEV",
             "labels": [{"name": "build:windows"}, {"name": "build:linux"}, {"name": "keep-me"}]},
        ], repo_labels=("build:linux", "build:windows", "build:macos-arm64", "build:macos-x86_64"))
        code, out = self.run_cli(["integrate", "--no-fetch", "--no-train", "--data", self.data(), "--push", "--build",
                                  "--os", "linux,macos-arm64"], gh=gh)
        self.assertEqual(code, 0, out)
        self.assertEqual([command[:2] for command, _ in calls],
                         [["pr", "list"], ["label", "list"], ["pr", "edit"]])
        edit, ci_at_edit = calls[2]
        self.assertEqual(edit[:3], ["pr", "edit", "6"])
        self.assertEqual(edit[edit.index("--add-label") + 1], "build:macos-arm64")
        self.assertEqual(edit[edit.index("--remove-label") + 1], "build:windows")
        # Set before the push, so the push builds the new set.
        self.assertIsNone(ci_at_edit)
        self.assertIn("the push started the Cosmyx dev build", out)

    def test_os_leaves_matching_labels_alone(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        gh, calls = self.fake_gh([
            {"number": 6, "url": "https://github.com/Owner/Repo/pull/6", "baseRefName": "cosmyx-ci/DEV",
             "labels": [{"name": "build:linux"}]},
        ], repo_labels=("build:linux",))
        code, out = self.run_cli(["integrate", "--no-fetch", "--no-train", "--data", self.data(), "--push", "--build",
                                  "--os", "linux"], gh=gh)
        self.assertEqual(code, 0, out)
        self.assertEqual([command[:2] for command, _ in calls], [["pr", "list"], ["label", "list"]])

    def test_os_is_validated_before_any_work(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        for value in ("linux,solaris", "", " , "):
            with self.subTest(value=value), self.assertRaises(cli.SetupError):
                self.run_cli(["integrate", "--no-fetch", "--data", self.data(), "--push", "--build", "--os", value])
        with self.assertRaises(cli.SetupError):
            self.run_cli(["integrate", "--no-fetch", "--data", self.data(), "--push", "--os", "linux"])
        self.assertFalse((self.work / ".worktrees").exists())

    def test_build_reuses_the_open_pull_request_and_closes_stale_ones_first(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        gh, calls = self.fake_gh([
            {"number": 5, "url": "https://github.com/Owner/Repo/pull/5", "baseRefName": "cosmyx-ci/v1"},
            {"number": 6, "url": "https://github.com/Owner/Repo/pull/6", "baseRefName": "cosmyx-ci/DEV"},
            {"number": 8, "url": "https://github.com/Owner/Repo/pull/8", "baseRefName": "DEV"},
        ])
        code, out = self.run_cli(["integrate", "--no-fetch", "--no-train", "--data", self.data(), "--push", "--build"],
                                 gh=gh)
        self.assertEqual(code, 0, out)
        self.assertEqual([command[:3] for command, _ in calls], [["pr", "list", "--head"], ["pr", "close", "5"]])
        # Closed before the push, so the push does not build it.
        self.assertIsNone(calls[1][1])
        self.assertIn("reused): https://github.com/Owner/Repo/pull/6", out)
        self.assertIn("the push started the Cosmyx dev build", out)
        self.assertEqual(self.remote_sha("cosmyx-ci/DEV"), self.git(["rev-parse", "origin/DEV"]))

    def test_build_stops_when_gh_fails(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)

        def gh(command):
            return subprocess.CompletedProcess(command, 1, "", "auth required")

        with self.assertRaises(cli.SetupError):
            self.run_cli(["integrate", "--no-fetch", "--no-train", "--data", self.data(), "--push", "--build"], gh=gh)
        self.assertIsNone(self.remote_sha("ci/cosmyx-integration"))

    def test_push_refuses_when_the_remote_moved(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.push("ci/cosmyx-integration")
        self.git(["fetch", "-q", "origin"])
        # Someone else pushes after our fetch, from their own clone, so our
        # remote-tracking ref stays at the old tip whatever the git version.
        other = self.tmp / "other"
        self.git(["clone", "-q", str(self.origin), str(other)], cwd=self.tmp)
        self.git(["checkout", "-q", "-B", "other", "origin/DEV"], cwd=other)
        (other / "src" / "other.txt").write_bytes(b"o\n")
        self.git(["add", "-A"], cwd=other)
        self.git(["commit", "-q", "-m", "other"], cwd=other)
        self.git(["push", "-q", "--force", "origin", "HEAD:refs/heads/ci/cosmyx-integration"], cwd=other)
        before = self.git(["rev-parse", "refs/remotes/origin/ci/cosmyx-integration"])
        self.assertNotEqual(before, self.git(["ls-remote", str(self.origin), "refs/heads/ci/cosmyx-integration"]).split()[0])
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

    def test_branch_not_on_the_remote_is_skipped_with_a_warning(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        code, out = self.run_cli(["integrate", "--no-fetch", "--data",
                                  self.data([{"name": "feat/not-pushed", "parent": "DEV"}])])
        self.assertEqual(code, 0, out)
        self.assertIn("warning: origin/feat/not-pushed not found, skipped", out)
        self.assertNotIn("| feat/not-pushed", out)
        self.assertEqual(self.integration_file("src/a.txt"), "a")

    def test_missing_base_changes_nothing(self) -> None:
        with self.assertRaises(cli.SetupError):
            self.run_cli(["integrate", "origin/gone", "--no-fetch", "--data", self.data()])
        self.assertFalse((self.work / ".worktrees").exists())

    def test_bundle_keeps_only_the_branches_of_that_bundle_or_earlier(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.branch("feat/b", "chore/foundation", {"src/b.txt": "b\n"}, from_ref=self.base)
        self.rows[-1]["bundle"] = 2
        code, out = self.run_cli(["integrate", "--no-fetch", "--data", self.data(), "--bundle", "1"])
        self.assertEqual(code, 0, out)
        self.assertIn("bundle 1: 2 branch(es) of bundle 1 or earlier", out)
        self.assertIn("| feat/a", out)
        self.assertNotIn("feat/b", out)
        self.assertEqual(self.integration_file("src/a.txt"), "a")
        self.assertNotIn("src/b.txt", self.git(["ls-tree", "-r", "--name-only", "ci/cosmyx-integration"]))

    def test_without_bundle_every_branch_is_kept(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.branch("feat/b", "chore/foundation", {"src/b.txt": "b\n"}, from_ref=self.base)
        self.rows[-1]["bundle"] = 2
        code, out = self.run_cli(["integrate", "--no-fetch", "--data", self.data()])
        self.assertEqual(code, 0, out)
        self.assertNotIn("bundle", out)
        self.assertEqual(self.integration_file("src/b.txt"), "b")

    def test_a_parent_in_a_later_bundle_is_refused_before_any_work(self) -> None:
        self.branch("feat/a", "chore/foundation", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.rows[-1]["bundle"] = 2
        self.branch("feat/a-child", "feat/a", {"src/c.txt": "c\n"}, from_ref=self.base)
        with self.assertRaisesRegex(cli.SetupError, r"feat/a-child \(bundle 1\): parent feat/a is in the later "
                                                    r"bundle 2"):
            self.run_cli(["integrate", "--no-fetch", "--data", self.data(), "--bundle", "1"])
        self.assertFalse((self.work / ".worktrees").exists())


class ReplayIntegrateTests(Sandbox):
    """`integrate` on a base that is not the list's: replay, then merge the replayed branches."""

    def setUp(self) -> None:
        super().setUp()
        start = self.base
        # DEV moved on after the release: a commit the tag does not have.
        self.commit({"src/dev-only.txt": "dev\n"}, "dev only")
        self.push("DEV")
        self.base = self.git(["rev-parse", "HEAD"])
        self.foundation()
        # Release tag on the old DEV, with one upstream change.
        self.git(["checkout", "-q", "-B", "release", start])
        self.commit({"src/app.txt": "one\ntwo upstream\nthree\n", "src/up.txt": "up\n"}, "upstream release")
        self.git(["tag", "v1"])
        self.git(["checkout", "-q", "DEV"])
        self.git(["fetch", "-q", "origin"])

    def run_v1(self, *extra: str, **kwargs) -> tuple[int, str]:
        return self.run_cli(["integrate", "v1", "--no-fetch", "--no-train", "--data", self.data(), *extra], **kwargs)

    def file_at(self, ref: str, path: str) -> str:
        return self.git(["show", f"{ref}:{path}"])

    def test_branches_are_replayed_onto_the_base_then_merged(self) -> None:
        self.branch("feat/a", "DEV", {"src/a.txt": "a\n"}, from_ref=self.base)
        self.branch("feat/a-child", "feat/a", {"src/child.txt": "c\n"}, from_ref=self.git(["rev-parse", "origin/feat/a"]))
        code, out = self.run_v1("--push")
        self.assertEqual(code, 0, out)
        v1 = self.git(["rev-parse", "v1^{commit}"])
        # Each branch's own commits, on BASE (foundation) or on its replayed parent.
        self.assertEqual(self.git(["rev-parse", "rebase/v1/chore/foundation~1"]), v1)
        self.assertEqual(self.git(["rev-parse", "rebase/v1/feat/a~1"]), self.git(["rev-parse", "rebase/v1/chore/foundation"]))
        self.assertEqual(self.git(["rev-parse", "rebase/v1/feat/a-child~1"]), self.git(["rev-parse", "rebase/v1/feat/a"]))
        # The integration merges the replayed branches, like the hand-made release integrations.
        subjects = self.git(["log", "--first-parent", "--format=%s", "integration/v1"]).splitlines()
        self.assertEqual(subjects[:3], ["Merge branch 'rebase/v1/feat/a-child' into integration/v1",
                                        "Merge branch 'rebase/v1/feat/a' into integration/v1",
                                        "Merge branch 'rebase/v1/chore/foundation' into integration/v1"])
        self.assertEqual(self.git(["rev-parse", "integration/v1~3"]), v1)
        # DEV's own commits are not dragged in.
        self.assertNotIn("src/dev-only.txt", self.git(["ls-tree", "-r", "--name-only", "integration/v1"]))
        self.assertEqual(self.file_at("integration/v1", "src/child.txt"), "c")
        self.assertEqual(self.file_at("integration/v1", "src/app.txt"), "one\ntwo upstream\nthree")
        # Only the integration branch and the CI base are pushed, not the rebase branches.
        self.assertEqual(self.remote_sha("integration/v1"), self.git(["rev-parse", "integration/v1"]))
        self.assertEqual(self.git(["ls-remote", str(self.origin), "refs/heads/rebase/*"]), "")
        self.assertIn("replayed 1", out)

    def remote_sha(self, branch: str) -> str | None:
        line = self.git(["ls-remote", str(self.origin), f"refs/heads/{branch}"])
        return line.split()[0] if line else None

    def test_unknown_replay_conflict_stops_and_a_recorded_resolution_is_replayed(self) -> None:
        self.branch("feat/clash", "DEV", {"src/app.txt": "one\ntwo mine\nthree\n"}, from_ref=self.base)
        self.branch("feat/later", "DEV", {"src/later.txt": "l\n"}, from_ref=self.base)
        code, out = self.run_v1()
        self.assertEqual(code, 1, out)
        self.assertIn("UNKNOWN CONFLICT in origin/feat/clash", out)
        self.assertIn("src/app.txt", out)
        self.assertIn("rerere", out)
        worktree = self.work / ".worktrees" / "integration-v1"
        wt = cli.Git(worktree)
        # The cherry-pick is left in progress so that the resolution can be recorded.
        self.assertIsNotNone(wt.sha("CHERRY_PICK_HEAD"))
        self.assertIsNone(cli.Git(self.work).sha("refs/heads/rebase/v1/feat/later"))
        (worktree / "src" / "app.txt").write_bytes(b"one\ntwo upstream\ntwo mine\nthree\n")
        self.git(["-c", "rerere.enabled=true", "rerere"], cwd=worktree)
        self.git(["cherry-pick", "--abort"], cwd=worktree)
        code, out = self.run_v1()
        self.assertEqual(code, 0, out)
        self.assertIn("rerere", out)
        self.assertEqual(self.file_at("integration/v1", "src/app.txt"), "one\ntwo upstream\ntwo mine\nthree")
        self.assertEqual(self.file_at("integration/v1", "src/later.txt"), "l")

    def test_a_hand_resolved_commit_is_reused_in_later_runs(self) -> None:
        # The release moved a file the branch edits (modify/delete: rerere cannot record it).
        self.git(["checkout", "-q", "release"])
        self.git(["rm", "-q", "src/app.txt"])
        self.commit({"src/all.txt": "one\ntwo upstream\nthree\n"}, "release moves app.txt")
        self.git(["tag", "-f", "v1"])
        self.git(["checkout", "-q", "DEV"])
        self.branch("feat/edit", "DEV", {"src/app.txt": "one\ntwo\nthree\nfour\n", "src/test.txt": "reads app\n"},
                    from_ref=self.base)
        self.branch("feat/later", "feat/edit", {"src/later.txt": "l\n"},
                    from_ref=self.git(["rev-parse", "origin/feat/edit"]))
        code, out = self.run_v1()
        self.assertEqual(code, 1, out)
        self.assertIn("modify/delete", out)
        self.assertIn("cherry-pick --continue", out)
        worktree = self.work / ".worktrees" / "integration-v1"
        # Resolved by hand: the edit goes to the moved file, and the test follows it.
        self.git(["rm", "-q", "src/app.txt"], cwd=worktree)
        (worktree / "src" / "all.txt").write_bytes(b"one\ntwo upstream\nthree\nfour\n")
        (worktree / "src" / "test.txt").write_bytes(b"reads all\n")
        self.git(["add", "src/all.txt", "src/test.txt"], cwd=worktree)
        self.git(["-c", "core.editor=true", "cherry-pick", "--continue"], cwd=worktree)
        code, out = self.run_v1("--push")
        self.assertEqual(code, 0, out)
        self.assertIn("earlier resolution", out)
        self.assertEqual(self.file_at("integration/v1", "src/all.txt"), "one\ntwo upstream\nthree\nfour")
        self.assertEqual(self.file_at("integration/v1", "src/test.txt"), "reads all")
        self.assertEqual(self.file_at("integration/v1", "src/later.txt"), "l")
        # A fresh clone state: no local rebase branches, worktree elsewhere; the pushed integration carries it.
        self.git(["worktree", "remove", "--force", str(worktree)])
        for ref in self.git(["for-each-ref", "--format=%(refname:short)", "refs/heads/rebase/"]).split():
            self.git(["branch", "-q", "-D", ref])
        self.git(["fetch", "-q", "origin"])
        code, out = self.run_cli(["integrate", "v1", "--no-fetch", "--no-train", "--data", self.data()])
        self.assertEqual(code, 0, out)
        self.assertIn("earlier resolution", out)
        self.assertEqual(self.file_at("integration/v1", "src/test.txt"), "reads all")
        # The replayed commit still names the branch's original commit, once.
        message = self.git(["log", "-1", "--format=%B", "rebase/v1/feat/edit"])
        self.assertEqual(message.count(cli.PICKED), 1)
        self.assertIn(cli.PICKED + self.git(["rev-parse", "origin/feat/edit"]), message)

    def test_known_conflict_kinds_are_resolved_during_the_replay(self) -> None:
        self.branch("feat/a", "DEV", {"CHANGELOG.md": self.changelog_with(("T17", "a."))}, from_ref=self.base)
        # A sibling written against an older feat/a: its replay conflicts in the changelog slots.
        self.git(["checkout", "-q", "-B", "feat/a2", self.base])
        self.commit({"CHANGELOG.md": self.changelog_with(("T17", "a."))}, "old a")
        self.commit({"CHANGELOG.md": self.changelog_with(("T17", "a."), ("T21", "a2."))}, "a2")
        self.push("feat/a2")
        self.git(["checkout", "-q", "DEV"])
        self.rows.append({"name": "feat/a2", "parent": "feat/a"})
        code, out = self.run_v1()
        self.assertEqual(code, 0, out)
        self.assertEqual(list(resolve.marker_order(self.file_at("integration/v1", "CHANGELOG.md"))),
                         ["T0", "T21", "T17", "T5"])

    def test_a_rerere_resolution_that_copies_the_source_file_whole_stops(self) -> None:
        self.branch("feat/clash", "DEV", {"src/app.txt": "one\ntwo mine\nthree\n"}, from_ref=self.base)
        code, out = self.run_v1()
        self.assertEqual(code, 1, out)
        worktree = self.work / ".worktrees" / "integration-v1"
        # A bad recorded resolution: the branch's whole file, which drops the release's own change.
        (worktree / "src" / "app.txt").write_bytes(b"one\ntwo mine\nthree\n")
        self.git(["-c", "rerere.enabled=true", "rerere"], cwd=worktree)
        self.git(["cherry-pick", "--abort"], cwd=worktree)
        code, out = self.run_v1()
        self.assertEqual(code, 1, out)
        source = self.git(["rev-parse", "origin/feat/clash"])
        self.assertIn("UNKNOWN CONFLICT in origin/feat/clash", out)
        self.assertIn("src/app.txt", out)
        self.assertIn(f"copied {source[:10]}'s whole file", out)
        self.assertIn("git rerere forget src/app.txt", out)
        self.assertEqual(cli.Git(worktree).sha("CHERRY_PICK_HEAD"), source)
        # A path allowed on purpose goes through.
        self.git(["cherry-pick", "--abort"], cwd=worktree)
        code, out = self.run_v1("--allow-whole-copy", "src/app.txt")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.file_at("integration/v1", "src/app.txt"), "one\ntwo mine\nthree")

    def test_an_earlier_resolution_that_copies_the_source_file_whole_is_not_reused(self) -> None:
        self.branch("feat/clash", "DEV", {"src/app.txt": "one\ntwo mine\nthree\n"}, from_ref=self.base)
        code, out = self.run_v1()
        self.assertEqual(code, 1, out)
        worktree = self.work / ".worktrees" / "integration-v1"
        (worktree / "src" / "app.txt").write_bytes(b"one\ntwo mine\nthree\n")
        self.git(["add", "src/app.txt"], cwd=worktree)
        self.git(["-c", "core.editor=true", "cherry-pick", "--continue"], cwd=worktree)
        # Only the committed bad replay is left to reuse, not what rerere learned.
        shutil.rmtree(self.work / ".git" / "rr-cache", ignore_errors=True)
        code, out = self.run_v1()
        self.assertEqual(code, 1, out)
        source = self.git(["rev-parse", "origin/feat/clash"])
        self.assertIn("src/app.txt", out)
        self.assertIn(f"copied {source[:10]}'s whole file", out)
        self.assertIn("earlier resolution", out)
        wt = cli.Git(worktree)
        # The bad replay is dropped and the source commit's cherry-pick is left in progress.
        self.assertEqual(wt.sha("CHERRY_PICK_HEAD"), source)
        self.assertEqual(wt.sha("HEAD"), self.git(["rev-parse", "rebase/v1/chore/foundation"]))

    def test_a_good_earlier_resolution_is_still_reused(self) -> None:
        self.branch("feat/clash", "DEV", {"src/app.txt": "one\ntwo mine\nthree\n"}, from_ref=self.base)
        self.run_v1()
        worktree = self.work / ".worktrees" / "integration-v1"
        (worktree / "src" / "app.txt").write_bytes(b"one\ntwo upstream\ntwo mine\nthree\n")
        self.git(["add", "src/app.txt"], cwd=worktree)
        self.git(["-c", "core.editor=true", "cherry-pick", "--continue"], cwd=worktree)
        shutil.rmtree(self.work / ".git" / "rr-cache", ignore_errors=True)
        code, out = self.run_v1()
        self.assertEqual(code, 0, out)
        self.assertIn("earlier resolution", out)
        self.assertEqual(self.file_at("integration/v1", "src/app.txt"), "one\ntwo upstream\ntwo mine\nthree")

    def big_change_branch(self) -> None:
        tail = "".join(f"added {number}\n" for number in range(50))
        self.branch("feat/big", "DEV", {"src/app.txt": "one\ntwo\nthree\n" + tail}, from_ref=self.base)

    def test_drift_from_the_base_is_warned_in_a_table(self) -> None:
        self.big_change_branch()
        code, out = self.run_v1("--push")
        self.assertEqual(code, 0, out)
        self.assertIn("DRIFT WARNING", out)
        rows = [line for line in out.splitlines() if line.startswith("| src/app.txt")]
        self.assertEqual(len(rows), 1, out)
        self.assertIn("| 50 ", rows[0])
        self.assertIsNotNone(self.remote_sha("integration/v1"))

    def test_strict_drift_stops_before_the_push(self) -> None:
        self.big_change_branch()
        code, out = self.run_v1("--push", "--strict-drift")
        self.assertEqual(code, 1, out)
        self.assertIn("src/app.txt", out)
        self.assertIsNone(self.remote_sha("integration/v1"))

    def test_drift_threshold_is_configurable(self) -> None:
        self.big_change_branch()
        code, out = self.run_v1("--strict-drift", "--drift-threshold", "60")
        self.assertEqual(code, 0, out)
        self.assertNotIn("DRIFT WARNING", out)

    def test_integration_branch_held_by_another_clean_worktree_is_reused(self) -> None:
        self.branch("feat/a", "DEV", {"src/a.txt": "a\n"}, from_ref=self.base)
        holder = self.work / ".worktrees" / "rebase-v1" / "integration"
        self.git(["worktree", "add", "-q", "-b", "integration/v1", str(holder), "v1"])
        code, out = self.run_v1()
        self.assertEqual(code, 0, out)
        self.assertIn(str(holder), out)
        self.assertFalse((self.work / ".worktrees" / "integration-v1").exists())
        self.assertEqual(self.file_at("integration/v1", "src/a.txt"), "a")
        self.assertEqual(self.git(["status", "--porcelain"], cwd=holder), "")

    def test_a_stopped_replay_keeps_the_branch_in_its_worktree(self) -> None:
        self.branch("feat/clash", "DEV", {"src/app.txt": "one\ntwo mine\nthree\n"}, from_ref=self.base)
        holder = self.work / ".worktrees" / "rebase-v1" / "integration"
        self.git(["worktree", "add", "-q", "-b", "integration/v1", str(holder), "v1"])
        code, out = self.run_v1()
        self.assertEqual(code, 1, out)
        # The next run must find the same worktree, not create the default one.
        self.assertEqual(cli.branch_holder(cli.Git(self.work), "integration/v1").resolve(), holder.resolve())
        self.assertIsNotNone(cli.Git(holder).sha("CHERRY_PICK_HEAD"))

    def test_integration_branch_held_by_a_dirty_worktree_is_refused_with_its_path(self) -> None:
        self.branch("feat/a", "DEV", {"src/a.txt": "a\n"}, from_ref=self.base)
        holder = self.work / ".worktrees" / "rebase-v1" / "integration"
        self.git(["worktree", "add", "-q", "-b", "integration/v1", str(holder), "v1"])
        (holder / "src" / "app.txt").write_bytes(b"dirty\n")
        with self.assertRaises(cli.SetupError) as raised:
            self.run_v1()
        self.assertIn(str(holder), str(raised.exception))

    def test_rebase_branch_held_by_a_clean_worktree_moves_with_it(self) -> None:
        self.branch("feat/a", "DEV", {"src/a.txt": "a\n"}, from_ref=self.base)
        holder = self.work / ".worktrees" / "rebase-v1" / "feat-a"
        self.git(["worktree", "add", "-q", "-b", "rebase/v1/feat/a", str(holder), "v1"])
        code, out = self.run_v1()
        self.assertEqual(code, 0, out)
        self.assertEqual(self.git(["rev-parse", "HEAD"], cwd=holder), self.git(["rev-parse", "rebase/v1/feat/a"]))
        self.assertEqual(self.git(["status", "--porcelain"], cwd=holder), "")
        self.assertEqual((holder / "src" / "a.txt").read_text(encoding="utf-8"), "a\n")

    def test_rebase_branch_held_by_a_dirty_worktree_is_refused_with_its_path(self) -> None:
        self.branch("feat/a", "DEV", {"src/a.txt": "a\n"}, from_ref=self.base)
        holder = self.work / ".worktrees" / "rebase-v1" / "feat-a"
        self.git(["worktree", "add", "-q", "-b", "rebase/v1/feat/a", str(holder), "v1"])
        (holder / "src" / "app.txt").write_bytes(b"dirty\n")
        with self.assertRaises(cli.SetupError) as raised:
            self.run_v1()
        self.assertIn(str(holder), str(raised.exception))


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

    def test_bundle_leaves_later_bundles_out_of_the_table(self) -> None:
        self.branch("feat/later", "DEV", {"src/later.txt": "l\n"}, from_ref=self.base)
        self.rows[-1]["bundle"] = 2
        code, out = self.run_cli(["rebase-check", "v1", "--no-fetch", "--data", self.data(), "--bundle", "1"])
        self.assertNotIn("feat/later", out)
        code, out = self.run_cli(["rebase-check", "v1", "--no-fetch", "--data", self.data()])
        self.assertIn("feat/later", out)

    def test_branch_not_on_the_remote_is_a_warning(self) -> None:
        self.branch("feat/a", "DEV", {"src/a.txt": "a\n"}, from_ref=self.base)
        code, out = self.run_cli(["rebase-check", "v1", "--no-fetch", "--data",
                                  self.data([{"name": "feat/not-pushed", "parent": "DEV"}])])
        self.assertEqual(code, 0, out)
        self.assertIn("missing on the remote, skipped", out)

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


class GuardTests(Sandbox):
    """The whole-file copy check and the drift table on a small history."""

    def setUp(self) -> None:
        super().setUp()
        self.wt = cli.Git(self.work)

    def test_copied_whole_needs_the_source_file_over_a_different_file(self) -> None:
        start = self.base
        self.git(["checkout", "-q", "-B", "source", start])
        source = self.commit({"src/app.txt": "one\ntwo mine\nthree\n"}, "source")
        self.git(["checkout", "-q", "-B", "head", start])
        head = self.commit({"src/app.txt": "one upstream\ntwo\nthree\n"}, "head")
        theirs = self.wt.blob_id(source, "src/app.txt")
        self.assertTrue(cli.copied_whole(self.wt, "src/app.txt", source, head, theirs))
        # The HEAD file is the source's parent file: taking the source file is the change itself.
        self.assertFalse(cli.copied_whole(self.wt, "src/app.txt", source, start, theirs))
        # A real merge of both changes is not a copy.
        (self.work / "merged.txt").write_bytes(b"one upstream\ntwo mine\nthree\n")
        merged = self.git(["hash-object", "merged.txt"])
        self.assertFalse(cli.copied_whole(self.wt, "src/app.txt", source, head, merged))
        # A path the source commit does not have.
        self.assertFalse(cli.copied_whole(self.wt, "src/none.txt", source, head, theirs))

    def test_drift_rows_skip_owned_new_allowed_and_small_paths(self) -> None:
        many = "".join(f"line {number}\n" for number in range(50))
        start = self.commit({
            "src/big.txt": "big\n", "src/small.txt": "small\n", "src/Cosmyx/own.txt": "own\n",
            "scripts/cosmyx-tool.sh": "tool\n", "wiki/page.md": "page\n", "cosmyx-src/data.txt": "data\n",
            ".github/workflows/build_orca.yml": "build\n",
        }, "start")
        tip = self.commit({
            "src/big.txt": "big\n" + many, "src/small.txt": "small\nsmall\n", "src/Cosmyx/own.txt": "own\n" + many,
            "scripts/cosmyx-tool.sh": "tool\n" + many, "wiki/page.md": "page\n" + many,
            "cosmyx-src/data.txt": "data\n" + many, ".github/workflows/build_orca.yml": "build\n" + many,
            "src/new.txt": many, "CHANGELOG.md": CHANGELOG + many,
        }, "tip")
        self.assertEqual(cli.drift_rows(self.wt, start, tip, 40), [("src/big.txt", "50", "0")])
        self.assertEqual(cli.drift_rows(self.wt, start, tip, 50), [])
        self.assertEqual(cli.drift_rows(self.wt, start, tip, 40, allowed=()),
                         [(".github/workflows/build_orca.yml", "50", "0"), ("src/big.txt", "50", "0")])

    def test_cosmyx_owned_paths(self) -> None:
        for path in ("src/slic3r/GUI/Cosmyx/a.cpp", "scripts/cosmyx/x.py", ".github/workflows/cosmyx-build.yml",
                     "wiki/x.md", ".claude/a.md", "CHANGELOG.md", "cosmyx-src/branding/a.json"):
            self.assertTrue(cli.cosmyx_owned(path), path)
        for path in ("src/slic3r/plugin/PluginManager.cpp", "justfile", "src/cosmyxless.cpp", "docs/CHANGELOG.md"):
            self.assertFalse(cli.cosmyx_owned(path), path)


class BranchListTests(unittest.TestCase):
    def test_shipped_list_is_ordered(self) -> None:
        data, entries = cli.load_branches()
        self.assertEqual(entries[0].name, data["foundation"])
        self.assertTrue(entries[-1].integration_only)
        self.assertEqual(len({entry.name for entry in entries}), len(entries))

    def test_shipped_list_has_the_ci_branches(self) -> None:
        names = [entry.name for entry in cli.load_branches()[1]]
        for name in ("ci/cosmyx-integrate", "ci/cosmyx-mac-retry", "ci/cosmyx-dev-build"):
            self.assertIn(name, names)
        # Superseded by the dev build (#119).
        self.assertNotIn("ci/cosmyx-arm64-pr-builds", names)
        self.assertLess(names.index("ci/cosmyx-mac-retry"), names.index("ci/cosmyx-dev-build"))

    def test_shipped_list_has_the_gui_feature_branches_after_their_parents(self) -> None:
        entries = {entry.name: entry for entry in cli.load_branches()[1]}
        names = list(entries)
        self.assertEqual(entries["feat/cosmyx-external-machines"].parent, "chore/cosmyx-foundation")
        self.assertEqual(entries["feat/cosmyx-update-check"].parent, "feat/cosmyx-version")
        self.assertLess(names.index("feat/cosmyx-version"), names.index("feat/cosmyx-update-check"))
        self.assertLess(names.index("chore/cosmyx-foundation"), names.index("feat/cosmyx-external-machines"))

    def test_shipped_list_stacks_the_languages_on_the_translations_fill(self) -> None:
        # feat/cosmyx-languages merges feat/cosmyx-translations-fill, so its own
        # commits are only those after the fill tip; a foundation parent would
        # replay the whole fill a second time.
        entries = {entry.name: entry for entry in cli.load_branches()[1]}
        names = list(entries)
        self.assertEqual(entries["feat/cosmyx-languages"].parent, "feat/cosmyx-translations-fill")
        self.assertLess(names.index("feat/cosmyx-translations-fill"), names.index("feat/cosmyx-languages"))
        self.assertEqual(entries["docs/cosmyx-changelogs"].parent, "chore/cosmyx-foundation")

    def test_shipped_list_stacks_the_machine_hook_chain_and_the_profiles(self) -> None:
        # The printer connection builds on the machine hook, which builds on the
        # models submenu; the profiles merge feat/cht-nozzle, so their own commits
        # are only those after the nozzle tip and the nozzle commits replay once.
        entries = {entry.name: entry for entry in cli.load_branches()[1]}
        names = list(entries)
        for child, parent in (("feat/cosmyx-machine-hook", "feat/cosmyx-models"),
                              ("feat/cosmyx-printer-connection", "feat/cosmyx-machine-hook"),
                              ("feat/cosmyx-profiles", "feat/cht-nozzle")):
            self.assertEqual(entries[child].parent, parent)
            self.assertLess(names.index(parent), names.index(child))

    def test_ci_base_branch_names(self) -> None:
        git = cli.Git(Path.cwd())
        self.assertEqual(cli.ci_base_branch(git, "origin/DEV", "origin"), "cosmyx-ci/DEV")
        self.assertEqual(cli.ci_base_branch(git, "DEV", "origin"), "cosmyx-ci/DEV")
        self.assertEqual(cli.ci_base_branch(git, "v2.5.2", "origin"), "cosmyx-ci/v2.5.2")
        self.assertEqual(cli.ci_base_branch(git, "refs/tags/v2.5.2", "origin"), "cosmyx-ci/v2.5.2")
        with self.assertRaises(cli.SetupError):
            cli.ci_base_branch(git, "origin/DEV~1", "origin")

    def test_integration_target_names(self) -> None:
        git = cli.Git(Path.cwd())
        self.assertEqual(cli.integration_target(git, "origin/DEV", "origin", "DEV"),
                         ("ci/cosmyx-integration", Path(".worktrees") / "integration"))
        self.assertEqual(cli.integration_target(git, "v2.5.2", "origin", "DEV"),
                         ("integration/v2.5.2", Path(".worktrees") / "integration-v2.5.2"))
        self.assertEqual(cli.integration_target(git, "origin/release/v2.5.3", "origin", "DEV"),
                         ("integration/release/v2.5.3", Path(".worktrees") / "integration-release-v2.5.3"))
        with self.assertRaises(cli.SetupError):
            cli.integration_target(git, "origin/DEV~1", "origin", "DEV")

    def test_shipped_list_gives_every_branch_a_bundle_and_no_parent_a_later_one(self) -> None:
        data = json.loads(cli.DATA_FILE.read_text(encoding="utf-8"))
        rows = {row["name"]: row for row in data["branches"]}
        for name, row in rows.items():
            self.assertIn(row.get("bundle"), (8, 9), name)
            if row["parent"] != data["base"]:
                self.assertLessEqual(rows[row["parent"]]["bundle"], row["bundle"], name)

    def test_shipped_bundle_8_is_the_bundle_7_parity_and_the_tooling(self) -> None:
        # Decision 0226: bundle 8 holds only the bundle-7 features rebased on
        # OrcaSlicer 2.5.2 plus the integration and build tooling.
        names = {entry.name for entry in cli.load_branches(bundle=8)[1]}
        self.assertEqual(names, {
            "chore/cosmyx-foundation", "ci/cosmyx-upstream-sync", "feat/cht-nozzle", "feat/ironing-temperature",
            "fix/toolchange-fan-order", "feat/cosmyx-models", "feat/cosmyx-version", "feat/cosmyx-stealth-mode",
            "feat/cosmyx-translations", "feat/cosmyx-translations-fill", "feat/cosmyx-windows-signing",
            "feat/cosmyx-update-check", "feat/cosmyx-profiles", "feat/cosmyx-machine-hook",
            "ci/cosmyx-artifact-checks", "ci/cosmyx-macos-signing", "ci/cosmyx-exec-smoke", "ci/cosmyx-flatpak-off",
            "ci/cosmyx-integrate", "ci/cosmyx-mac-retry", "ci/cosmyx-dev-build", "docs/cosmyx-changelogs",
            "docs/cosmyx-rebase-skill"})
        self.assertEqual(len(cli.load_branches(bundle=9)[1]), len(cli.load_branches()[1]))

    def write_list(self, rows: list[dict]) -> Path:
        temp = Path(tempfile.mkdtemp(prefix="cosmyx-integrate-list-"))
        self.addCleanup(shutil.rmtree, temp, True)
        path = temp / "branches.json"
        path.write_text(json.dumps({"base": "DEV", "foundation": "f", "branches": rows}), encoding="utf-8")
        return path

    def test_a_row_without_a_valid_bundle_is_refused(self) -> None:
        for bad in ({}, {"bundle": None}, {"bundle": "8"}, {"bundle": True}, {"bundle": 0}, {"bundle": 1.5}):
            with self.subTest(bad=bad), self.assertRaisesRegex(cli.SetupError, "f: bundle must be a positive"):
                cli.load_branches(self.write_list([{"name": "f", "parent": "DEV", **bad}]))

    def test_bundle_selection_keeps_the_order_and_rechecks_the_subset(self) -> None:
        path = self.write_list([{"name": "f", "parent": "DEV", "bundle": 1},
                                {"name": "b", "parent": "f", "bundle": 2},
                                {"name": "a", "parent": "DEV", "bundle": 1},
                                {"name": "c", "parent": "a", "bundle": 3}])
        self.assertEqual([entry.name for entry in cli.load_branches(path, 1)[1]], ["f", "a"])
        self.assertEqual([entry.name for entry in cli.load_branches(path, 2)[1]], ["f", "b", "a"])
        self.assertEqual([entry.name for entry in cli.load_branches(path)[1]], ["f", "b", "a", "c"])
        with self.assertRaisesRegex(cli.SetupError, "--bundle must be a positive integer"):
            cli.load_branches(path, 0)
        # The subset is checked on its own: a subset that loses its parent is refused.
        data = {"base": "DEV", "foundation": "f"}
        with self.assertRaisesRegex(cli.SetupError, "c: parent a must be DEV or an earlier row"):
            cli.select_bundle(data, [cli.Entry("f", "DEV"), cli.Entry("a", "DEV", bundle=2),
                                     cli.Entry("c", "a", bundle=1)], 1)

    def test_a_parent_in_a_later_bundle_is_refused(self) -> None:
        data = {"base": "DEV", "foundation": "f"}
        with self.assertRaisesRegex(cli.SetupError, r"c \(bundle 8\): parent p is in the later bundle 9"):
            cli.check_branches(data, [cli.Entry("f", "DEV", bundle=8), cli.Entry("p", "DEV", bundle=9),
                                      cli.Entry("c", "p", bundle=8)])

    def test_child_before_parent_is_refused(self) -> None:
        data = {"base": "DEV", "foundation": "f"}
        with self.assertRaises(cli.SetupError):
            cli.check_branches(data, [cli.Entry("f", "DEV"), cli.Entry("c", "p"), cli.Entry("p", "DEV")])
        with self.assertRaises(cli.SetupError):
            cli.check_branches(data, [cli.Entry("f", "DEV"), cli.Entry("f", "DEV")])


if __name__ == "__main__":
    unittest.main()
