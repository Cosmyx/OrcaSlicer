"""Breaker test for upstream_sync.py remote_sha: `git ls-remote <remote>
refs/heads/<branch>` matches ref names by their tail, so another branch whose
name ends in /refs/heads/<branch> is listed too, and sorts first."""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_upstream_sync import sync  # noqa: E402

GIT_ENV = {
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
    "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
    "GITHUB_STEP_SUMMARY": "", "GITHUB_OUTPUT": "",
}


class RemoteShaSuffixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cosmyx-breaker-sync-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        patcher = mock.patch.dict(os.environ, GIT_ENV)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.work = self.tmp / "work"
        self.git("init", "-q", "-b", "main", str(self.work))
        self.upstream, self.origin = self.tmp / "upstream.git", self.tmp / "origin.git"
        for bare in (self.upstream, self.origin):
            self.git("init", "-q", "--bare", str(bare))

    def git(self, *args: str, cwd: Path | None = None) -> str:
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, message: str) -> str:
        self.git("commit", "-q", "--allow-empty", "-m", message, cwd=self.work)
        return self.git("rev-parse", "HEAD", cwd=self.work)

    def push(self, remote: Path, rev: str, branch: str) -> None:
        self.git("push", "-q", "--force", str(remote), f"{rev}:refs/heads/{branch}", cwd=self.work)

    def test_remote_sha_ignores_branches_that_only_end_like_the_target(self) -> None:
        """Expected: remote_sha(origin, "Orca-Upstream") is the tip of
        refs/heads/Orca-Upstream. Actual: it returns the tip of
        refs/heads/0/refs/heads/Orca-Upstream, listed first by ls-remote (sorted by ref name)."""
        old = self.commit("old")
        new = self.commit("new")
        self.push(self.origin, old, "Orca-Upstream")
        self.push(self.origin, new, "0/refs/heads/Orca-Upstream")
        self.assertEqual(sync.remote_sha(str(self.origin), "Orca-Upstream"), old)

    def test_remote_sha_is_none_when_only_a_look_alike_exists(self) -> None:
        tip = self.commit("only look-alike")
        self.push(self.origin, tip, "0/refs/heads/Orca-Upstream")
        self.assertIsNone(sync.remote_sha(str(self.origin), "Orca-Upstream"))

    def test_mirror_is_not_fooled_by_a_look_alike_branch(self) -> None:
        """Expected: Orca-Upstream is stale, so mirror moves it to the upstream
        tip. Actual: a branch named 0/refs/heads/Orca-Upstream already at the
        upstream tip makes mirror report "already up to date" and push nothing,
        so Orca-Upstream (and MIXED) silently stop following upstream."""
        old = self.commit("upstream 1")
        new = self.commit("upstream 2")
        self.push(self.upstream, new, "main")
        self.push(self.origin, old, "Orca-Upstream")
        self.push(self.origin, new, "0/refs/heads/Orca-Upstream")
        with redirect_stdout(io.StringIO()):
            sync.mirror(str(self.upstream), "main", str(self.origin), "Orca-Upstream")
        tip = self.git("rev-parse", "refs/heads/Orca-Upstream", cwd=self.origin)
        self.assertEqual(tip, new)


if __name__ == "__main__":
    unittest.main()
