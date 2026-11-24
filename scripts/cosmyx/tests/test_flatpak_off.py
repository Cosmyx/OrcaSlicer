"""The Flatpak build stays off unless the COSMYX_FLATPAK repository variable
turns it on (decision 0213)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build_flatpak.yml"
GATE = "if: ${{ vars.COSMYX_FLATPAK == 'true' }}"


def jobs(text: str) -> dict[str, str]:
    """Split the jobs: section into {job id: job body} on two-space keys."""
    section = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([A-Za-z0-9_-]+):\n", section, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


def own_keys(body: str) -> dict[str, str]:
    """The job-level keys (four-space indent) of a job body."""
    return dict(re.findall(r"^    ([a-z-]+):(.*)$", body, flags=re.MULTILINE))


class FlatpakOffTests(unittest.TestCase):
    def setUp(self) -> None:
        # Read as bytes: a CRLF checkout (Windows runner) must not hide the line.
        self.text = WORKFLOW.read_bytes().decode("utf-8").replace("\r\n", "\n")
        self.jobs = jobs(self.text)

    def test_flatpak_job_is_gated_by_the_repository_variable(self) -> None:
        keys = own_keys(self.jobs["flatpak"])
        self.assertIn("if", keys)
        self.assertEqual(f"if:{keys['if']}".split(" # ")[0].strip(), GATE)

    def test_gate_is_one_tagged_line(self) -> None:
        lines = [line for line in self.text.splitlines() if "COSMYX_FLATPAK" in line]
        self.assertEqual(len(lines), 1)
        self.assertIn("# Cosmyx:", lines[0])

    def test_unit_test_jobs_still_need_the_flatpak_job(self) -> None:
        test_jobs = [name for name, body in self.jobs.items() if "unit_tests_flatpak.yml" in body]
        self.assertEqual(len(test_jobs), 2)
        for name in test_jobs:
            keys = own_keys(self.jobs[name])
            self.assertEqual(keys.get("needs", "").strip(), "flatpak", name)
            # A skipped flatpak job must skip the tests, not run them.
            self.assertIn("success()", keys.get("if", ""), name)


if __name__ == "__main__":
    unittest.main()
