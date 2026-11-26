"""The hand-recoloured raster overlays, and the rasters that keep their
upstream look (decision 0214)."""

from __future__ import annotations

import json
import struct
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BRANDING = REPO_ROOT / "cosmyx-src" / "branding"
OVERLAY = BRANDING / "overlay"

RECOLOURED = (
    "resources/images/texture_displacement/erase.gif",
    "resources/images/texture_displacement/painted_only_off.png",
    "resources/images/texture_displacement/painted_only_on.png",
    "resources/images/texture_displacement/select_all.png",
    "resources/images/texture_displacement/smart_fill_angle_high.png",
    "resources/images/texture_displacement/smart_fill_angle_low.png",
    "resources/images/texture_displacement/view_fast.png",
    "resources/images/texture_displacement/view_wireframe.png",
    "resources/web/guide/11/earth.png",
    "resources/web/homepage/img/i4.png",
    "resources/web/homepage/img/i5.png",
    "resources/web/model/img/null.png",
    "resources/web/model/img/null2.png",
)

KEPT_UPSTREAM = (
    "resources/images/bed_cool.png",
    "resources/images/big_bed_cool.png",
    "resources/images/bed_cool_supertack.png",
    "resources/images/big_bed_cool_supertack.png",
    "resources/images/bed_pei_cool.png",
    "resources/images/big_bed_pei_cool.png",
    "resources/textures/displacement/Hex Tiles.png",
    "resources/web/orca/setup_connection.gif",
)


def pixel_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"GIF8"):
        return struct.unpack("<HH", data[6:10])
    raise AssertionError(f"{path}: not a PNG or GIF")


def manifest_rows() -> dict[str, dict]:
    rows = {}
    for manifest in (BRANDING / "manifest").glob("*.json"):
        for row in json.loads(manifest.read_text(encoding="utf-8"))["rows"]:
            rows[row["path"]] = row
    return rows


class RasterOverlayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rows = manifest_rows()

    def test_recoloured_rasters_have_an_overlay_of_the_upstream_size(self) -> None:
        for path in RECOLOURED:
            with self.subTest(path=path):
                self.assertTrue((OVERLAY / path).is_file())
                self.assertEqual(pixel_size(OVERLAY / path), pixel_size(REPO_ROOT / path))

    def test_recoloured_rasters_are_recorded_as_recolours(self) -> None:
        for path in RECOLOURED:
            with self.subTest(path=path):
                row = self.rows[path]
                self.assertEqual(row["kind"], "recolour")
                self.assertIn(row["status"], ("to-validate", "validated"))

    def test_kept_rasters_have_no_overlay(self) -> None:
        for path in KEPT_UPSTREAM:
            with self.subTest(path=path):
                self.assertTrue((REPO_ROOT / path).is_file(), "upstream file moved: update decision 0214")
                self.assertFalse((OVERLAY / path).exists())

    def test_erase_animation_keeps_its_frames(self) -> None:
        path = "resources/images/texture_displacement/erase.gif"
        marker = b"\x21\xf9\x04"  # graphic control extension, one per frame
        self.assertEqual(
            (OVERLAY / path).read_bytes().count(marker), (REPO_ROOT / path).read_bytes().count(marker)
        )


if __name__ == "__main__":
    unittest.main()
