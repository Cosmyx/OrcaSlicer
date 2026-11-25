"""Checks of the versioned changelogs under cosmyx-src/changelog/."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CHANGELOG_DIR = REPO_ROOT / "cosmyx-src" / "changelog"
BUNDLE_HEADING = re.compile(
    r"^\*\*=+ UNDER THIS, IT'S THE CONTENT ADDED BY BUNDLE (\d+) =+\*\*$", re.MULTILINE
)
DATED_BULLET = re.compile(r"^- \*\*(\d{4}-\d{2}-\d{2})\*\* — \S")


class ChangelogFilesTests(unittest.TestCase):
    def test_both_changelogs_exist(self) -> None:
        for name in ("ORCASLICER.md", "COSMYX.md"):
            with self.subTest(name=name):
                self.assertTrue((CHANGELOG_DIR / name).is_file())


class CosmyxChangelogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (CHANGELOG_DIR / "COSMYX.md").read_text(encoding="utf-8")

    def test_bundles_start_at_one_and_increase_by_one(self) -> None:
        bundles = [int(number) for number in BUNDLE_HEADING.findall(self.text)]
        self.assertTrue(bundles)
        self.assertEqual(bundles, list(range(1, len(bundles) + 1)))

    def test_every_bundle_marker_line_follows_the_pattern(self) -> None:
        # A marker with a typo would silently drop out of the bundle list.
        for line in self.text.splitlines():
            if "CONTENT ADDED BY BUNDLE" in line:
                with self.subTest(line=line):
                    self.assertRegex(line, BUNDLE_HEADING)


class OrcaSlicerChangelogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (CHANGELOG_DIR / "ORCASLICER.md").read_text(encoding="utf-8")

    def test_sections_are_in_order(self) -> None:
        sections = re.findall(r"^## (.+)$", self.text, flags=re.MULTILINE)
        self.assertEqual(sections, ["Added", "Changed", "Fixed", "Removed"])

    def test_bullets_are_dated_and_newest_first(self) -> None:
        for section in re.split(r"^## ", self.text, flags=re.MULTILINE)[1:]:
            name = section.splitlines()[0]
            bullets = [line for line in section.splitlines() if line.startswith("- ")]
            with self.subTest(section=name):
                self.assertTrue(bullets)
                dates = []
                for line in bullets:
                    match = DATED_BULLET.match(line)
                    self.assertIsNotNone(match, line)
                    dates.append(match.group(1))
                self.assertEqual(dates, sorted(dates, reverse=True))


if __name__ == "__main__":
    unittest.main()
