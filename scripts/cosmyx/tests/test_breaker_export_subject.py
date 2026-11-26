"""Breaker test for artifact_checks/cli.py export_subject (the `local` command):
data files whose names are not plain ASCII."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import cli  # noqa: E402

GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
}


class ExportSubjectTests(unittest.TestCase):
    def test_non_ascii_model_name_is_exported_under_its_real_name(self) -> None:
        """Expected: resources/cosmyx/models/cube-été.stl of the commit is
        written at the same path in the subject folder. Actual: `git ls-tree
        --name-only` without -z C-quotes non-ASCII names (core.quotePath), so
        export_subject asks `git show` for the quoted name, gets nothing and
        writes an empty file named '"resources/cosmyx/models/cube-...\\303\\251...stl"'."""
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, GIT_ENV):
            repo, target = Path(tmp) / "repo", Path(tmp) / "subject"
            name = "cube-été.stl"
            model = repo / "resources" / "cosmyx" / "models" / name
            model.parent.mkdir(parents=True)
            model.write_bytes(b"solid cube\nendsolid cube\n")
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "model"], check=True)
            sha = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True,
                                 text=True).stdout.strip()
            with mock.patch.object(cli, "REPO_ROOT", repo):
                self.assertTrue(cli.export_subject(sha, target))
            exported = target / "resources" / "cosmyx" / "models" / name
            self.assertTrue(exported.is_file(), sorted(p.as_posix() for p in target.rglob("*")))
            self.assertEqual(exported.read_bytes(), model.read_bytes())


if __name__ == "__main__":
    unittest.main()
