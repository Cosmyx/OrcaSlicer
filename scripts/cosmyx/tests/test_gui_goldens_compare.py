"""compare: Linux byte-exact, Windows and macOS within tolerance.json."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gui_goldens import GUI_DIR, GoldenError  # noqa: E402
from gui_goldens import compare  # noqa: E402
from gui_goldens import png  # noqa: E402

TOLERANT = compare.Tolerance(exact=False, channel_delta=8, max_diff_ratio=0.0005, tile=16, max_tile_ratio=0.10)


def flat(width: int, height: int, value: int = 100) -> png.Image:
    return png.Image(width, height, bytes((value, value, value, 255)) * (width * height))


def with_pixels(image: png.Image, pixels: dict[tuple[int, int], tuple[int, int, int, int]]) -> png.Image:
    data = bytearray(image.rgba)
    for (x, y), rgba in pixels.items():
        i = (y * image.width + x) * 4
        data[i:i + 4] = bytes(rgba)
    return png.Image(image.width, image.height, bytes(data))


class ToleranceFileTests(unittest.TestCase):
    def test_shipped_tolerances(self) -> None:
        linux = compare.load_tolerance(GUI_DIR / "tolerance.json", "linux")
        self.assertTrue(linux.exact)
        self.assertFalse(linux.webview_mask)
        for os_name in ("windows", "macos"):
            with self.subTest(os=os_name):
                tolerance = compare.load_tolerance(GUI_DIR / "tolerance.json", os_name)
                self.assertFalse(tolerance.exact)
                self.assertEqual(tolerance.channel_delta, 8)
                self.assertEqual(tolerance.max_diff_ratio, 0.0005)
                self.assertEqual(tolerance.tile, 16)
                self.assertEqual(tolerance.max_tile_ratio, 0.10)
                self.assertTrue(tolerance.webview_mask)

    def test_bad_files_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "t.json"
            path.write_text(json.dumps({"version": 1, "linux": {"mode": "fuzzy"}}), encoding="utf-8")
            with self.assertRaises(GoldenError):
                compare.load_tolerance(path, "linux")
            with self.assertRaises(GoldenError):
                compare.load_tolerance(path, "windows")

    def test_stability_uses_half_the_tolerance(self) -> None:
        half = compare.halved(TOLERANT)
        self.assertEqual(half.channel_delta, 4)
        self.assertAlmostEqual(half.max_diff_ratio, 0.00025)
        self.assertAlmostEqual(half.max_tile_ratio, 0.05)


class ImageTests(unittest.TestCase):
    def test_identical_images_pass_everywhere(self) -> None:
        self.assertTrue(compare.compare_images(flat(4, 4), flat(4, 4), compare.Tolerance()).ok)

    def test_exact_mode_fails_on_one_byte(self) -> None:
        changed = with_pixels(flat(4, 4), {(1, 1): (101, 100, 100, 255)})
        self.assertFalse(compare.compare_images(flat(4, 4), changed, compare.Tolerance()).ok)

    def test_size_change_fails_in_both_modes(self) -> None:
        for tolerance in (compare.Tolerance(), TOLERANT):
            diff = compare.compare_images(flat(4, 4), flat(4, 5), tolerance)
            self.assertFalse(diff.ok)
            self.assertIn("size", diff.reason)

    def test_small_channel_moves_are_not_differences(self) -> None:
        moved = with_pixels(flat(100, 100), {(x, 0): (108, 92, 100, 255) for x in range(100)})
        diff = compare.compare_images(flat(100, 100), moved, TOLERANT)
        self.assertTrue(diff.ok)
        self.assertEqual(diff.differing, 0)

    def test_ratio_limit(self) -> None:
        base = flat(200, 100)  # 20000 pixels: 0.05 % is 10 pixels
        spread = {(x * 20, y * 20): (0, 0, 0, 255) for x in range(10) for y in range(1)}
        self.assertTrue(compare.compare_images(base, with_pixels(base, spread), TOLERANT).ok)
        spread[(5, 50)] = (0, 0, 0, 255)
        diff = compare.compare_images(base, with_pixels(base, spread), TOLERANT)
        self.assertFalse(diff.ok)
        self.assertEqual(diff.differing, 11)

    def test_tile_limit_catches_a_small_local_change(self) -> None:
        base = flat(400, 400)  # 160000 pixels: 0.05 % is 80 pixels
        blob = {(x, y): (0, 0, 0, 255) for x in range(6) for y in range(5)}  # 30 px in one 16x16 tile (11.7 %)
        diff = compare.compare_images(base, with_pixels(base, blob), TOLERANT)
        self.assertFalse(diff.ok)
        self.assertIn("tile", diff.reason)
        smaller = {(x, y): (0, 0, 0, 255) for x in range(5) for y in range(5)}  # 25 px: 9.8 %
        self.assertTrue(compare.compare_images(base, with_pixels(base, smaller), TOLERANT).ok)


class DirectoryTests(unittest.TestCase):
    def test_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            golden, actual = Path(tmp) / "g", Path(tmp) / "a"
            for folder in (golden, actual):
                folder.mkdir()
                png.write(folder / "00-same.png", flat(3, 3))
                (folder / "environment.json").write_text("{}", encoding="utf-8")
            png.write(golden / "10-changed.png", flat(3, 3))
            png.write(actual / "10-changed.png", flat(3, 3, 0))
            png.write(golden / "20-gone.png", flat(3, 3))
            png.write(actual / "30-new.png", flat(3, 3))
            (golden / "20-menu-tree.txt").write_text("File\n", encoding="utf-8")
            (actual / "20-menu-tree.txt").write_text("File \n", encoding="utf-8")
            results = {r.name: r.status for r in compare.compare_dirs(golden, actual, TOLERANT)}
        self.assertEqual(results, {"00-same.png": "pass", "10-changed.png": "fail", "20-gone.png": "gone",
                                   "30-new.png": "missing", "20-menu-tree.txt": "fail"})

    def test_no_goldens_never_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp)
            self.assertFalse(compare.passed(compare.compare_dirs(empty, empty, TOLERANT)))


if __name__ == "__main__":
    unittest.main()
