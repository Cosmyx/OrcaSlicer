"""Breaker tests for the Info.plist readers: smoke_native.app_executable
(artifact checks) and macos_signing.dmg.volume_name (DMG rebuild)."""

from __future__ import annotations

import plistlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import smoke_native  # noqa: E402
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

    def test_app_executable_with_a_non_dict_plist_falls_back(self) -> None:
        """Expected: a valid plist whose root is not a dictionary is treated like
        a missing one (the bundle's own name). Actual: plistlib returns a list and
        `.get` raises AttributeError out of app_executable, ending the macOS job."""
        self.write_plist(["not", "a", "dict"])
        self.assertEqual(smoke_native.app_executable(self.app), self.app / "Contents" / "MacOS" / "OrcaSlicer")

    def test_app_executable_with_a_non_string_name_falls_back(self) -> None:
        """Expected: a CFBundleExecutable that is not a string is ignored.
        Actual: TypeError from `Path / 5`."""
        self.write_plist({"CFBundleExecutable": 5})
        self.assertEqual(smoke_native.app_executable(self.app), self.app / "Contents" / "MacOS" / "OrcaSlicer")

    def test_app_executable_stays_inside_the_bundle(self) -> None:
        """Expected: the executable that will be run is inside Contents/MacOS of
        the bundle. Actual: CFBundleExecutable "../../../../../tmp/x" is joined
        as is, so the smoke run would execute a file outside the app."""
        self.write_plist({"CFBundleExecutable": "../../../../../tmp/x"})
        exe = smoke_native.app_executable(self.app)
        macos_dir = (self.app / "Contents" / "MacOS").resolve()
        self.assertEqual(exe.resolve().parent, macos_dir, exe)

    def test_volume_name_with_a_non_dict_plist_falls_back(self) -> None:
        """Expected: the DMG volume name falls back to the app name for a plist
        whose root is not a dictionary. Actual: AttributeError (not a
        SigningError) escapes dmg.volume_name and the signing step dies with a
        traceback instead of its error line and summary."""
        self.write_plist(["not", "a", "dict"])
        self.assertEqual(dmg.volume_name(self.app), "OrcaSlicer")


if __name__ == "__main__":
    unittest.main()
