"""Tests of scripts/cosmyx/worktree_clean.py: hiding build-time edits of
tracked files from git diff with the skip-worktree bit."""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

COSMYX_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, COSMYX_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


wc = load_module("worktree_clean")

SPACED = "dir with space/file one.po"
UNICODE = "unicod\u00e9/\u00e9t\u00e9 \u2713.txt"


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def write(root: Path, relative: str, text: str) -> None:
    path = root.joinpath(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def read(root: Path, relative: str) -> str:
    return root.joinpath(*relative.split("/")).read_bytes().decode("utf-8")


class WorktreeCleanTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "core.autocrlf", "false")
        for name in (SPACED, UNICODE, "plain.txt", "kept.txt"):
            write(self.root, name, f"committed {name}\n")
        git(self.root, "add", "-A")
        self.assertEqual(git(self.root, "commit", "-q", "-m", "init").returncode, 0)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = wc.main(["--repo", str(self.root), *args])
        return code, out.getvalue(), err.getvalue()

    def is_clean(self) -> bool:
        return git(self.root, "diff", "--quiet", "HEAD").returncode == 0

    def edit_all(self) -> None:
        for name in (SPACED, UNICODE, "plain.txt"):
            write(self.root, name, f"grafted {name}\n")

    def test_hide_makes_the_diff_clean_and_keeps_the_edits_on_disk(self) -> None:
        self.edit_all()
        self.assertFalse(self.is_clean())
        code, _, err = self.run_main("hide")
        self.assertEqual(code, 0, err)
        self.assertTrue(self.is_clean())
        for name in (SPACED, UNICODE, "plain.txt"):
            self.assertEqual(read(self.root, name), f"grafted {name}\n")

    def test_show_lists_the_hidden_files_with_spaces_and_unicode(self) -> None:
        self.edit_all()
        self.run_main("hide")
        code, out, _ = self.run_main("show")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(out.splitlines()), sorted([SPACED, UNICODE, "plain.txt"]))

    def test_untracked_files_are_left_alone(self) -> None:
        write(self.root, "new file.txt", "untracked\n")
        code, _, err = self.run_main("hide")
        self.assertEqual(code, 0, err)
        self.assertTrue(self.is_clean())
        self.assertEqual(self.run_main("show")[1], "")
        self.assertIn("?? ", git(self.root, "status", "--porcelain").stdout.decode("utf-8"))

    def test_hide_on_a_clean_tree_is_a_no_op(self) -> None:
        code, out, _ = self.run_main("hide")
        self.assertEqual(code, 0)
        self.assertIn("Hid 0 ", out)
        self.assertEqual(self.run_main("show")[1], "")

    def test_hide_is_idempotent(self) -> None:
        self.edit_all()
        self.assertEqual(self.run_main("hide")[0], 0)
        first = self.run_main("show")[1]
        code, _, err = self.run_main("hide")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.run_main("show")[1], first)
        self.assertTrue(self.is_clean())

    def test_a_deleted_file_is_hidden_too(self) -> None:
        self.root.joinpath("plain.txt").unlink()
        self.assertEqual(self.run_main("hide")[0], 0)
        self.assertTrue(self.is_clean())

    def test_hide_fails_and_lists_a_staged_change(self) -> None:
        write(self.root, "plain.txt", "staged\n")
        git(self.root, "add", "plain.txt")
        code, _, err = self.run_main("hide")
        self.assertEqual(code, 1)
        self.assertIn("plain.txt", err)

    def test_unhide_restores_the_committed_content(self) -> None:
        self.edit_all()
        self.run_main("hide")
        code, _, err = self.run_main("unhide")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.run_main("show")[1], "")
        for name in (SPACED, UNICODE, "plain.txt"):
            self.assertEqual(read(self.root, name), f"committed {name}\n")
        self.assertTrue(self.is_clean())

    def test_unhide_with_a_pathspec_only_touches_those_files(self) -> None:
        self.edit_all()
        self.run_main("hide")
        code, _, err = self.run_main("unhide", "dir with space")
        self.assertEqual(code, 0, err)
        self.assertEqual(read(self.root, SPACED), f"committed {SPACED}\n")
        self.assertEqual(read(self.root, "plain.txt"), "grafted plain.txt\n")
        self.assertEqual(sorted(self.run_main("show")[1].splitlines()), sorted([UNICODE, "plain.txt"]))

    def test_unhide_with_nothing_hidden_is_a_no_op(self) -> None:
        code, out, _ = self.run_main("unhide")
        self.assertEqual(code, 0)
        self.assertIn("Restored 0 ", out)

    def test_outside_a_repository_is_a_git_error(self) -> None:
        with tempfile.TemporaryDirectory() as other:
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                code = wc.main(["--repo", other, "show"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
