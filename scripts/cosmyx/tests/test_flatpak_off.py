"""The Flatpak build stays off unless the COSMYX_FLATPAK repository variable
turns it on (decision 0213)."""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

COSMYX_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = COSMYX_DIR.parents[1]
GATE_TERM = "vars.COSMYX_FLATPAK == 'true'"

spec = importlib.util.spec_from_file_location("workflow_jobs", COSMYX_DIR / "workflow_jobs.py")
workflow_jobs = importlib.util.module_from_spec(spec)
sys.modules["workflow_jobs"] = workflow_jobs
spec.loader.exec_module(workflow_jobs)


def is_gated(if_value: str) -> bool:
    """True when a job's `if:` value is the gate alone, or the gate as the
    leading term of a top-level `&&` chain, so it holds for the whole condition.

    The gate is a standalone `if:` where the job had none (build_flatpak.yml
    on DEV) and is merged into the job's own condition where it has one
    (build_all.yml on older tags).
    """
    expr = if_value.split(" # ")[0].strip()
    match = re.fullmatch(r"\$\{\{\s*(.*?)\s*\}\}", expr)
    if not match:
        return False
    inner = match.group(1)
    if inner == GATE_TERM:
        return True
    if not inner.startswith(GATE_TERM + " && "):
        return False
    # A top-level || would let the rest of the condition bypass the gate.
    depth = 0
    for index, char in enumerate(inner):
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth == 0 and inner.startswith("||", index):
            return False
    return True


class GateTests(unittest.TestCase):
    def test_standalone_gate(self) -> None:
        self.assertTrue(is_gated(" ${{ vars.COSMYX_FLATPAK == 'true' }} # Cosmyx: off"))

    def test_gate_leading_an_existing_condition(self) -> None:
        value = " ${{ vars.COSMYX_FLATPAK == 'true' && !cancelled() && (a || b) }} # Cosmyx: off"
        self.assertTrue(is_gated(value))

    def test_gate_bypassed_by_a_top_level_or(self) -> None:
        self.assertFalse(is_gated(" ${{ vars.COSMYX_FLATPAK == 'true' && a || b }}"))

    def test_gate_not_leading(self) -> None:
        self.assertFalse(is_gated(" ${{ !cancelled() && vars.COSMYX_FLATPAK == 'true' }}"))

    def test_no_gate(self) -> None:
        self.assertFalse(is_gated(" ${{ !cancelled() }}"))


class FlatpakOffTests(unittest.TestCase):
    def setUp(self) -> None:
        # The job is in build_flatpak.yml on DEV, in build_all.yml on older tags.
        found = workflow_jobs.find_job(REPO_ROOT, "flatpak")
        if found is None:
            self.skipTest("this upstream base has no flatpak build job")
        self.path, self.text, self.jobs = found

    def test_flatpak_job_is_gated_by_the_repository_variable(self) -> None:
        keys = workflow_jobs.own_keys(self.jobs["flatpak"])
        self.assertIn("if", keys)
        self.assertTrue(is_gated(keys["if"]), keys["if"])

    def test_gate_is_one_tagged_line(self) -> None:
        lines = [line for line in self.text.splitlines() if "COSMYX_FLATPAK" in line]
        self.assertEqual(len(lines), 1, self.path.name)
        self.assertIn("# Cosmyx:", lines[0])

    def test_unit_test_jobs_still_need_the_flatpak_job(self) -> None:
        test_jobs = [name for name, body in self.jobs.items() if "unit_tests_flatpak.yml" in body]
        self.assertEqual(len(test_jobs), 2)
        for name in test_jobs:
            keys = workflow_jobs.own_keys(self.jobs[name])
            self.assertEqual(keys.get("needs", "").strip(), "flatpak", name)
            # A skipped flatpak job must skip the tests, not run them.
            self.assertIn("success()", keys.get("if", ""), name)


if __name__ == "__main__":
    unittest.main()
