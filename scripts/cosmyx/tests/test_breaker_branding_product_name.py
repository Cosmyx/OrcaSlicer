"""Breaker tests of the product-name stage (T11e): the token rule and the
translation check miss or wrongly rewrite some spellings of the upstream name.

Every test here reproduces one hole and fails until the stage is fixed.
"""

from __future__ import annotations

import re
import unittest

from branding_fixture import REPO_ROOT, branding

from branding.product_name import catalogues, tables, tokens  # noqa: E402

RENAME_FILE = REPO_ROOT / branding.PRODUCT_NAME_DIR / "rename.json"
# The upstream name glued to a grammatical suffix (Czech, Hungarian, Basque...).
INFLECTED = re.compile(r"Orca ?[Ss]licer[a-z\u00e0-\u024f]+")


class InflectedNameTest(unittest.TestCase):
    """Agglutinative and inflected languages glue a suffix to the name
    (cs "OrcaSliceru", hu "OrcaSlicerrel", eu "OrcaSlicerren"). The token
    rule refuses a match followed by a letter, so these stay untouched and
    the post guard (`visible_name`) does not see them either."""

    def test_suffixed_name_is_renamed(self) -> None:
        for text, lang in (
            ("verze OrcaSliceru.", "cs"),
            ("az OrcaSlicerrel", "hu"),
            ("OrcaSlicerren bertsioa", "eu"),
        ):
            with self.subTest(text=text):
                self.assertNotIn("OrcaSlicer", tokens.replace_tokens(text, lang))
                self.assertTrue(tokens.visible_name(text, lang))

    @unittest.skipUnless(RENAME_FILE.is_file(), "no product-name rename table on this branch")
    def test_real_renamed_translations_keep_no_inflected_name(self) -> None:
        """On the committed tables: every confirmed translation of a renamed
        msgid, once renamed, still showing an inflected OrcaSlicer."""
        rows = tables.rename_rows(branding.load_json(RENAME_FILE)["rows"])
        renamed = tables.mapping(rows, "msgid")
        left = []
        for relative in catalogues.catalogue_files(REPO_ROOT):
            lang = catalogues.language(relative)
            if lang is None:
                continue
            for entry in catalogues.read(REPO_ROOT, relative).messages():
                if entry.msgid not in renamed or entry.fuzzy:
                    continue
                for text in (entry.msgstr, *entry.msgstr_plural.values()):
                    if INFLECTED.search(tokens.replace_tokens(text, lang)):
                        left.append(f"{relative}: {entry.msgid[:50]!r}")
        self.assertEqual(left, [], f"{len(left)} renamed translation(s) still show the upstream name")


class UppercaseNameTest(unittest.TestCase):
    def test_uppercase_two_words(self) -> None:
        """"ORCA SLICER" becomes "CosmoSlice SLICER": ORCA matches alone."""
        self.assertEqual(tokens.replace_tokens("Welcome to ORCA SLICER"), "Welcome to CosmoSlice")

    def test_uppercase_one_word_is_visible(self) -> None:
        """"ORCASLICER" in visible text is neither renamed nor reported."""
        self.assertTrue(tokens.visible_name("WELCOME TO ORCASLICER"))


class KeptAppKeyNamesTest(unittest.TestCase):
    """Decision 0133: the data folder and the config file keep SLIC3R_APP_KEY
    (OrcaSlicer), so a visible text naming them keeps pointing at the real
    file. Decision 0210: the .app and the AppImage are named CosmoSlice, so a
    text naming them follows the new name."""

    def test_names_derived_from_the_app_key_stay(self) -> None:
        for text in (
            "Edit OrcaSlicer.conf by hand",
            "Data is in %APPDATA%\\OrcaSlicer",
            "Data is in C:\\Users\\me\\AppData\\Roaming\\OrcaSlicer",
        ):
            with self.subTest(text=text):
                self.assertEqual(tokens.replace_tokens(text), text)

    def test_package_names_follow_the_new_name(self) -> None:
        for text, expected in (
            ("Move OrcaSlicer.app to Applications", "Move CosmoSlice.app to Applications"),
            ("Run OrcaSlicer.AppImage", "Run CosmoSlice.AppImage"),
        ):
            with self.subTest(text=text):
                self.assertEqual(tokens.replace_tokens(text), expected)


class CombiningMarkTest(unittest.TestCase):
    def test_name_followed_by_combining_mark_is_a_different_word(self) -> None:
        """"Orca" + U+0301 is the word "Orcá": renaming it moves the accent
        onto the new name ("CosmoSlicé")."""
        text = "Orca\u0301 x"
        self.assertEqual(tokens.replace_tokens(text), text)


if __name__ == "__main__":
    unittest.main()
