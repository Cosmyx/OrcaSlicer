"""Breaker tests for upstream_sync.py is_scheduled: valid YAML that declares a
schedule trigger without a line starting with `schedule:` or `on: ...schedule`.
A miss lets an upstream bot workflow run on the fork unpoliced."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_upstream_sync import sync  # noqa: E402


class ScheduleDetectionTests(unittest.TestCase):
    def test_trigger_through_an_alias(self) -> None:
        """Expected: True (GitHub Actions accepts YAML anchors and aliases, and
        `on: *triggers` expands to a schedule). Actual: False, the anchor is
        defined on a line that starts with another key and the `on:` line only
        holds the alias."""
        text = ("x-triggers: &triggers {schedule: [{cron: '0 3 * * *'}], workflow_dispatch: {}}\n"
                "on: *triggers\n"
                "jobs:\n  stale:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n")
        self.assertTrue(sync.is_scheduled(text))

    def test_schedule_inside_a_multi_line_flow_mapping(self) -> None:
        """Expected: True. Actual: False, the `schedule:` key follows another key
        on a continuation line of the `on: {` flow mapping."""
        text = ("on: {\n"
                "  push: {branches: [main]}, schedule: [{cron: '0 3 * * *'}]\n"
                "}\n"
                "jobs:\n  stale:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n")
        self.assertTrue(sync.is_scheduled(text))


if __name__ == "__main__":
    unittest.main()
