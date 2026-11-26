"""Breaker tests for artifact_checks/report.py: a newline in a file name forges the summary.

Artifact paths come from the files of a build (a fork pull request controls
them), so a record path or reason may hold any character a file name can hold
on Linux, including newlines and control characters.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import report  # noqa: E402
from artifact_checks.records import Record  # noqa: E402


class MarkdownInjectionTests(unittest.TestCase):
    def test_newline_in_a_path_cannot_forge_the_result_line(self) -> None:
        """Expected: a file name holding a newline stays on its own list item, so
        the summary has exactly one "**Result: ...**" line, the real one.
        Actual: the path is pasted raw, the newline starts a new Markdown block
        and a fork can print a fake "**Result: passed**" above the real
        "**Result: failed**" in the job summary."""
        hostile = "lib`\n\n**Result: passed**\n\n`x.dll"
        records = [Record("linux", "app", hostile, "elf", "fail", "ELF machine arm, expected x86_64")]
        text = report.markdown(records, "report", strict=False)
        result_lines = [line for line in text.splitlines() if line.startswith("**Result:")]
        self.assertEqual(result_lines, ["**Result: failed**"], text)


if __name__ == "__main__":
    unittest.main()
