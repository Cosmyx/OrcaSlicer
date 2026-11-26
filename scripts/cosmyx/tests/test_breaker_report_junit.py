"""Breaker tests for artifact_checks/report.py: control characters in a file name break junit.xml.

Artifact paths come from the files of a build (a fork pull request controls
them), so a record path or reason may hold any character a file name can hold
on Linux, including newlines and control characters.
"""

from __future__ import annotations

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import report  # noqa: E402
from artifact_checks.records import Record  # noqa: E402


class JunitControlCharacterTests(unittest.TestCase):
    def test_control_characters_in_a_path_still_give_well_formed_xml(self) -> None:
        """Expected: junit.xml stays well-formed XML 1.0 whatever the file names
        (control characters dropped or replaced), so the test reporter can read
        it. Actual: ElementTree writes the raw U+001B into the name attribute and
        the result cannot be parsed back (ParseError: not well-formed)."""
        records = [Record("linux", "app", "bin/\x1b[31mred\x1b[0m", "elf", "fail", "bad \x01 reason")]
        xml_text = report.junit(records, strict=False)
        ET.fromstring(xml_text.split("\n", 1)[1])


if __name__ == "__main__":
    unittest.main()
