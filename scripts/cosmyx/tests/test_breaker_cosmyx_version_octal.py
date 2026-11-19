"""Breaker tests for cosmyx_version.py: numbers C++ and Python read differently."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_cosmyx_version import cv  # noqa: E402

HEADER = "namespace Cosmyx {{\ninline constexpr int patch_version = {patch};\n}}\n"
VERSION_INC = 'set(SLIC3R_APP_NAME "OrcaSlicer")\nset(SoftFever_VERSION "{version}")\n'


class VersionNumberTests(unittest.TestCase):
    def tree(self, version: str, patch: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / cv.VERSION_INC).write_text(VERSION_INC.format(version=version), encoding="utf-8")
        header = root / cv.VERSION_HEADER
        header.parent.mkdir(parents=True)
        header.write_text(HEADER.format(patch=patch), encoding="utf-8")
        return root

    def test_leading_zero_patch_is_not_read_as_decimal(self) -> None:
        """Expected: `patch_version = 010;` is rejected (or read as 8, its C++
        octal value), so the build names and the app's About box agree.
        Actual: Python reads 10 while the compiled app shows 8, and the
        artifacts are named 2.6.0-10 for an app that says 2.6.0-8."""
        root = self.tree("2.6.0", "010")
        try:
            value = cv.patch_version(root)
        except cv.VersionError:
            return
        self.assertEqual(value, 8)


if __name__ == "__main__":
    unittest.main()
