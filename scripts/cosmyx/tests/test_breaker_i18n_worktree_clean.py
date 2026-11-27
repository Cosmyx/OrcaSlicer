"""Breaker tests of scripts/cosmyx/worktree_clean.py (the hide step of the
i18n graft and the branding).

Every test here reproduces one hole and fails until the helper is fixed.
"""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

COSMYX_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, COSMYX_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


wc = load_module("worktree_clean")


def git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


class GlobNameTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.name", "Test")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "core.autocrlf", "false")
        (self.root / "x[ab].txt").write_bytes(b"committed glob\n")
        (self.root / "xa.txt").write_bytes(b"committed plain\n")
        git(self.root, "add", "-A")
        self.assertEqual(git(self.root, "commit", "-q", "-m", "init").returncode, 0)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_unhide_restores_only_the_hidden_files(self) -> None:
        """unhide feeds the hidden paths to `git checkout` as pathspecs, so a
        name holding glob characters (`x[ab].txt`, valid on every OS) also
        matches `xa.txt` and silently discards an edit to that file."""
        (self.root / "x[ab].txt").write_bytes(b"grafted\n")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(wc.main(["--repo", str(self.root), "hide"]), 0)
        (self.root / "xa.txt").write_bytes(b"work in progress\n")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(wc.main(["--repo", str(self.root), "unhide"]), 0)
        self.assertEqual((self.root / "x[ab].txt").read_bytes(), b"committed glob\n")
        self.assertEqual((self.root / "xa.txt").read_bytes(), b"work in progress\n")


if __name__ == "__main__":
    unittest.main()
