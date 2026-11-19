"""Breaker tests of the colour stage (T11c): the hex scan and the colours.json
validation.

Every test here reproduces one hole and fails until the stage is fixed.
"""

from __future__ import annotations

import unittest

from branding_fixture import branding

from branding import colours  # noqa: E402

TABLE = {"#009688": "#8000FF"}


class HexScanTest(unittest.TestCase):
    def test_url_fragment_is_not_a_colour(self) -> None:
        """`href="https://x.org/page#009688"`: only `href="#..."` is
        protected, so a URL fragment of six hex digits is recoloured and the
        link breaks."""
        data = b'<a href="https://example.org/page#009688">x</a>'
        self.assertEqual(colours.rewrite_hex(data, TABLE)[0], data)

    def test_numeric_character_reference_is_not_a_colour(self) -> None:
        """`&#129688;` (an emoji in HTML) reads as the teal #129688: G5 flags
        it as residue after apply and a mapping would rewrite it."""
        self.assertEqual(branding.find_hexes("<p>&#129688;</p>"), [])
        data = b"<p>&#009688;</p>"
        self.assertEqual(colours.rewrite_hex(data, TABLE)[0], data)


class PaletteValidationTest(unittest.TestCase):
    def test_invalid_palette_colours_are_problems(self) -> None:
        """Palette values are never checked. Guard G7 greps each one as a
        case-insensitive substring of every tracked file, so a short "#80F"
        matches any "#80F..." colour upstream, and "#GGGGGG" is no colour."""
        for value in ("#80F", "#GGGGGG", "8000FF", "#8000FF80"):
            with self.subTest(value=value):
                problems = colours.table_problems({"palette": {"brand": value}, "mappings": []})
                self.assertTrue(problems, f"palette {value!r} accepted")


if __name__ == "__main__":
    unittest.main()
