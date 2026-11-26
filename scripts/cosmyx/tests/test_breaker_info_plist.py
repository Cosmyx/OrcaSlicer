"""Breaker tests for the Info.plist reader of the DMG rebuild:
macos_signing.dmg.volume_name."""

from __future__ import annotations

import plistlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from macos_signing import dmg  # noqa: E402


class InfoPlistTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.app = Path(tmp.name) / "mnt" / "OrcaSlicer.app"
        (self.app / "Contents" / "MacOS").mkdir(parents=True)

    def write_plist(self, value) -> None:
        with open(self.app / "Contents" / "Info.plist", "wb") as handle:
            plistlib.dump(value, handle)

    def test_volume_name_with_a_non_dict_plist_falls_back(self) -> None:
        """Expected: the DMG volume name falls back to the app name for a plist
        whose root is not a dictionary. Actual: AttributeError (not a
        SigningError) escapes dmg.volume_name and the signing step dies with a
        traceback instead of its error line and summary."""
        self.write_plist(["not", "a", "dict"])
        self.assertEqual(dmg.volume_name(self.app), "OrcaSlicer")


if __name__ == "__main__":
    unittest.main()
