"""Checks of workflow_jobs: the flatpak job is found in either upstream layout."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

COSMYX_DIR = Path(__file__).resolve().parents[1]

spec = importlib.util.spec_from_file_location("workflow_jobs", COSMYX_DIR / "workflow_jobs.py")
workflow_jobs = importlib.util.module_from_spec(spec)
sys.modules["workflow_jobs"] = workflow_jobs
spec.loader.exec_module(workflow_jobs)

# DEV layout: build_all.yml only calls the reusable build_flatpak.yml.
CALLER = """name: Build all
on: push
jobs:
  build_linux:
    runs-on: ubuntu-24.04
    steps:
    - run: echo linux
  flatpak:
    uses: ./.github/workflows/build_flatpak.yml
"""

REUSABLE = """name: Build flatpak
on: workflow_call
jobs:
  flatpak:
    if: ${{ vars.COSMYX_FLATPAK == 'true' }} # Cosmyx: gate
    runs-on: ubuntu-24.04
    steps:
    - name: Package flatpak test asset
      run: |
        find "$d/resources" -mindepth 1 ! -name profiles ! -name cosmyx -exec rm -rf {} +
  unit_tests_flatpak_x86_64:
    needs: flatpak
    uses: ./.github/workflows/unit_tests_flatpak.yml
"""

# Older tag layout: the flatpak job sits inside build_all.yml, saved as CRLF.
INLINE = """name: Build all
on: push
jobs:
  build_linux:
    runs-on: ubuntu-24.04
    steps:
    - run: find "$d/resources" -name elsewhere -exec rm -rf {} +
  flatpak:
    if: ${{ vars.COSMYX_FLATPAK == 'true' && !cancelled() }} # Cosmyx: gate
    runs-on: ubuntu-24.04
    steps:
    - run: find "$d/resources" ! -name cosmyx -exec rm -rf {} +
  unit_tests_flatpak_x86_64:
    needs: flatpak
    uses: ./.github/workflows/unit_tests_flatpak.yml
"""


def make_tree(root: Path, files: dict[str, str], crlf: tuple[str, ...] = ()) -> None:
    workflows = root / ".github" / "workflows"
    workflows.mkdir(parents=True)
    for name, text in files.items():
        if name in crlf:
            text = text.replace("\n", "\r\n")
        (workflows / name).write_bytes(text.encode("utf-8"))


class FindJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_dev_layout_finds_the_reusable_workflow_not_its_caller(self) -> None:
        make_tree(self.root, {"build_all.yml": CALLER, "build_flatpak.yml": REUSABLE})
        path, _, found = workflow_jobs.find_job(self.root, "flatpak")
        self.assertEqual(path.name, "build_flatpak.yml")
        self.assertIn("! -name cosmyx", found["flatpak"])
        self.assertIn("unit_tests_flatpak_x86_64", found)

    def test_tag_layout_finds_the_job_inside_a_crlf_build_all(self) -> None:
        make_tree(self.root, {"build_all.yml": INLINE}, crlf=("build_all.yml",))
        path, text, found = workflow_jobs.find_job(self.root, "flatpak")
        self.assertEqual(path.name, "build_all.yml")
        self.assertNotIn("\r", text)
        # The job body stops at the next job: the other job's filter is not in it.
        self.assertNotIn("elsewhere", found["flatpak"])
        self.assertNotIn("unit_tests_flatpak.yml", found["flatpak"])
        self.assertIn("! -name cosmyx", found["flatpak"])
        keys = workflow_jobs.own_keys(found["flatpak"])
        self.assertIn("COSMYX_FLATPAK", keys["if"])

    def test_no_layout_returns_none(self) -> None:
        make_tree(self.root, {"build_all.yml": CALLER})
        self.assertIsNone(workflow_jobs.find_job(self.root, "flatpak"))

    def test_missing_workflows_folder_returns_none(self) -> None:
        self.assertIsNone(workflow_jobs.find_job(self.root, "flatpak"))

    def test_file_without_jobs_section_has_no_jobs(self) -> None:
        self.assertEqual(workflow_jobs.jobs("name: x\non: push\n"), {})


if __name__ == "__main__":
    unittest.main()
