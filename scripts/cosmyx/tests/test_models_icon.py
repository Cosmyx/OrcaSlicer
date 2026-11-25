"""Checks that the Cosmyx models menu icon uses the palette of its sibling
menu icons (menu_add_part.svg, menu_add_modifier.svg), so it looks native."""

from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
ICON = REPO_ROOT / "resources" / "images" / "menu_add_part_cosmyx.svg"

# Grey shape and violet plus badge of the sibling menu icons.
SIBLING_PALETTE = {"#949494", "#8000FF", "none"}
SVG_NS = "{http://www.w3.org/2000/svg}"


def paint_values(element: ET.Element) -> list[str]:
    """Return the fill and stroke values set on an element, attribute or style."""
    values = [element.get(name) for name in ("fill", "stroke") if element.get(name)]
    for declaration in (element.get("style") or "").split(";"):
        name, _, value = declaration.partition(":")
        if name.strip() in ("fill", "stroke"):
            values.append(value.strip())
    return values


class ModelsMenuIconTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = ET.parse(ICON).getroot()
        self.paths = list(self.root.iter(f"{SVG_NS}path"))

    def test_only_sibling_palette_colours(self) -> None:
        for element in self.root.iter():
            for value in paint_values(element):
                with self.subTest(element=element.get("id"), value=value):
                    self.assertIn(value, SIBLING_PALETTE)

    def test_every_path_is_painted(self) -> None:
        # A path without a fill renders black, which no sibling icon uses.
        self.assertEqual(len(self.paths), 4)
        for path in self.paths:
            with self.subTest(path=path.get("id")):
                self.assertTrue(paint_values(path), "path has no fill or stroke")

    def test_logo_is_grey_and_badge_is_violet(self) -> None:
        logo = [p for p in self.paths if (p.get("id") or "").startswith("path")]
        badge = [p for p in self.paths if p not in logo]
        self.assertEqual(len(logo), 3)
        self.assertEqual(len(badge), 1)
        for path in logo:
            self.assertIn("#949494", paint_values(path))
        self.assertIn("#8000FF", paint_values(badge[0]))


if __name__ == "__main__":
    unittest.main()
