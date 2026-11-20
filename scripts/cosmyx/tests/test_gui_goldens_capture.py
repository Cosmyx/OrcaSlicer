"""Per-OS capture backends: parsing with fake tools everywhere, and one real
capture on the OS the tests run on, when that OS allows it (skipped with the
reason otherwise)."""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import shutil
import struct
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gui_goldens import GoldenError, capture_linux, capture_mac  # noqa: E402
from gui_goldens.capture import Capturer  # noqa: E402


def xwd_dump(width: int, height: int, pixels: bytes, byte_order: int = 0, ncolors: int = 2) -> bytes:
    header_size = 100 + 8  # header plus an 8-byte window name
    fields = [header_size, 7, 2, 24, width, height, 0, byte_order, 32, byte_order, 32, 32, width * 4, 4,
              0xFF0000, 0xFF00, 0xFF, 8, ncolors, ncolors, width, height, 0, 0, 0]
    return struct.pack(">25I", *fields) + b"root\0\0\0\0" + b"\0" * (12 * ncolors) + pixels


def fake_run(outputs: dict[str, str]):
    def run(args, **kwargs):
        key = " ".join(args[:3])
        return subprocess.CompletedProcess(args, 0, outputs.get(key, ""), "")
    return run


class LinuxParsingTests(unittest.TestCase):
    def test_xwd_little_and_big_endian(self) -> None:
        little = capture_linux.parse_xwd(xwd_dump(2, 1, bytes((3, 2, 1, 0, 6, 5, 4, 0))))
        self.assertEqual(little.pixel(0, 0), (1, 2, 3, 255))
        big = capture_linux.parse_xwd(xwd_dump(1, 1, bytes((0, 1, 2, 3)), byte_order=1))
        self.assertEqual(big.pixel(0, 0), (1, 2, 3, 255))

    def test_bad_dumps(self) -> None:
        with self.assertRaises(GoldenError):
            capture_linux.parse_xwd(b"short")
        with self.assertRaises(GoldenError):
            capture_linux.parse_xwd(xwd_dump(2, 2, b"\0" * 4))

    def test_capture_crops_to_the_screen(self) -> None:
        dump = xwd_dump(4, 4, bytes(range(64)))
        run = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, dump, b"")
        image = capture_linux.capture_rect([-1, 2, 3, 5], run)
        self.assertEqual((image.width, image.height), (2, 2))

    def test_popup_is_the_topmost_override_redirect_window(self) -> None:
        tree = ("xwininfo: Window id: 0x1 (the root window)\n  3 children:\n"
                '     0x200001 "OrcaSlicer": ("orca-slicer" "OrcaSlicer")  1296x900+0+0  +16+48\n'
                "     0x400010 (has no name): ()  220x340+0+0  +100+120\n"
                "     0x400011 (has no name): ()  1x1+-1+-1  +-1+-1\n")
        stats = {"0x200001": "Map State: IsViewable\nOverride Redirect State: no\n",
                 "0x400010": "Map State: IsViewable\nOverride Redirect State: yes\n"}

        def run(args, **kwargs):
            if args[:2] == ["xwininfo", "-root"]:
                return subprocess.CompletedProcess(args, 0, tree, "")
            return subprocess.CompletedProcess(args, 0, stats.get(args[2], ""), "")

        self.assertEqual(capture_linux.popup_rect(run), [100, 120, 220, 340])


class MacParsingTests(unittest.TestCase):
    def test_points_from_pixels(self) -> None:
        self.assertEqual(capture_mac.points([20, 40, 200, 100], 2.0), [10, 20, 100, 50])

    def test_menu_windows_keep_menu_layer_only(self) -> None:
        listing = json.dumps([{"owner": "OrcaSlicer", "layer": 0, "bounds": {"X": 0, "Y": 0, "Width": 900, "Height": 600}},
                              {"owner": "OrcaSlicer", "layer": 101, "bounds": {"X": 5, "Y": 25, "Width": 200, "Height": 300}},
                              {"owner": "Dock", "layer": 101, "bounds": {"X": 0, "Y": 0, "Width": 4, "Height": 4}}])
        run = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, listing, "")
        self.assertEqual(capture_mac.menu_windows(run), [[5, 25, 200, 300]])

    def test_no_menu_is_an_error(self) -> None:
        run = lambda args, **kwargs: subprocess.CompletedProcess(args, 0, "[]", "")
        with self.assertRaises(GoldenError):
            capture_mac.wait_menu(run, timeout=0, sleep=lambda s: None)


class DispatchTests(unittest.TestCase):
    def test_every_os_has_a_backend(self) -> None:
        for os_name in ("linux", "macos", "windows"):
            self.assertEqual(Capturer(os_name).os, os_name)
        with self.assertRaises(GoldenError):
            Capturer("beos")


def mac_screen_recording_allowed() -> bool:
    """CGPreflightScreenCaptureAccess answers without asking the user."""
    library = ctypes.util.find_library("CoreGraphics")
    if not library:
        return False
    graphics = ctypes.cdll.LoadLibrary(library)
    if not hasattr(graphics, "CGPreflightScreenCaptureAccess"):
        return False
    graphics.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
    return bool(graphics.CGPreflightScreenCaptureAccess())


class RealCaptureTests(unittest.TestCase):
    def check(self, image) -> None:
        self.assertEqual((image.width, image.height), (8, 8))
        self.assertEqual(len(image.rgba), 8 * 8 * 4)

    @unittest.skipUnless(sys.platform == "darwin", "macOS only")
    def test_macos_screencapture(self) -> None:
        if not shutil.which("screencapture"):
            self.skipTest("screencapture is not installed")
        if not mac_screen_recording_allowed():
            self.skipTest("Screen Recording is not granted to this terminal (never requested by the tests)")
        self.check(Capturer("macos").rect([0, 0, 8, 8], 1.0))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux only")
    def test_linux_xwd(self) -> None:
        if not os.environ.get("DISPLAY") or not shutil.which("xwd"):
            self.skipTest("no X display or no xwd (the goldens image has both)")
        self.check(Capturer("linux").rect([0, 0, 8, 8], 1.0))

    @unittest.skipUnless(sys.platform == "win32", "Windows only")
    def test_windows_bitblt(self) -> None:
        self.check(Capturer("windows").rect([0, 0, 8, 8], 1.0))


if __name__ == "__main__":
    unittest.main()
