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

    def test_non_ascii_digits_are_rejected(self) -> None:
        """Expected: VersionError for a SoftFever_VERSION or patch_version written
        with non-ASCII digits (CMake and the C++ compiler do not read them as
        numbers). Actual: Python's \\d accepts them, so "2.6.\\uff10" passes and a
        fullwidth digit reaches the artifact names, and an Arabic-Indic 8 is
        taken as patch 8 although the header no longer compiles."""
        with self.assertRaises(cv.VersionError):
            cv.upstream_version(self.tree("2.6.０", "8"))
        with self.assertRaises(cv.VersionError):
            cv.patch_version(self.tree("2.6.0", "٨"))


if __name__ == "__main__":
    unittest.main()
