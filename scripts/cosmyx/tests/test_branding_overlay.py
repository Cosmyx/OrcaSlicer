"""Tests of the branding overlay and of the counted text patches."""

from __future__ import annotations

import unittest

from branding_fixture import TreeCase, branding, manifest, overlay, read, svg, textpatch, write


class OverlayTest(TreeCase):
    def test_targets_are_rows_with_an_override(self) -> None:
        self.assertEqual(overlay.targets(self.root, manifest.load(self.root)), [])
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        self.assertEqual(overlay.targets(self.root, manifest.load(self.root)), ["resources/images/apple.svg"])

    def test_copies_bytes_exactly(self) -> None:
        content = svg("#8000FF").replace("\n", "\r\n").encode("utf-8") + b"\xff"
        self.add_overlay("resources/images/OrcaSlicer_32px.png", content)
        written = overlay.apply(self.root, manifest.load(self.root))
        self.assertEqual(written, ["resources/images/OrcaSlicer_32px.png"])
        self.assertEqual(read(self.root, "resources/images/OrcaSlicer_32px.png"), content)

    def test_creates_a_file_upstream_lacks(self) -> None:
        self.add_overlay("resources/images/OrcaSlicer_new folder/OrcaSlicer \u00e9.svg", svg("#8000FF"))
        overlay.apply(self.root, manifest.load(self.root))
        self.assertTrue((self.root / "resources/images/OrcaSlicer_new folder/OrcaSlicer \u00e9.svg").is_file())

    def test_calls_back_before_each_write(self) -> None:
        self.add_overlay("resources/images/apple.svg", svg("#8000FF"))
        seen = []

        def before(path):
            seen.append((path, read(self.root, path)))

        original = read(self.root, "resources/images/apple.svg")
        overlay.apply(self.root, manifest.load(self.root), before)
        self.assertEqual(seen, [("resources/images/apple.svg", original)])

    def test_overlay_listing_skips_gitkeep(self) -> None:
        self.assertEqual(manifest.overlay_files(self.root), [])
        self.assertTrue((self.root / branding.OVERLAY_DIR / ".gitkeep").is_file())


class TextPatchTest(TreeCase):
    def patch(self, **values):
        row = {"file": "version.inc", "old": "OrcaSlicer", "new": "CosmoSlice", "count": 2, "reason": "name"}
        row.update(values)
        return textpatch.normalise(row)

    def test_applies_every_occurrence(self) -> None:
        self.assertEqual(textpatch.apply(self.root, [self.patch()]), ["version.inc"])
        self.assertEqual(read(self.root, "version.inc").count(b"CosmoSlice"), 2)

    def test_find_replace_spelling(self) -> None:
        row = textpatch.normalise({"file": "a", "find": "x", "replace": "y", "count": 1, "reason": "r"})
        self.assertEqual((row.old, row.new), ("x", "y"))

    def test_count_mismatch_writes_nothing(self) -> None:
        before = read(self.root, "version.inc"), read(self.root, "README.md")
        rows = [self.patch(file="README.md", count=1), self.patch(count=3)]
        with self.assertRaises(branding.BrandingError):
            textpatch.apply(self.root, rows)
        self.assertEqual((read(self.root, "version.inc"), read(self.root, "README.md")), before)

    def test_rows_on_one_file_apply_in_order(self) -> None:
        rows = [self.patch(old='"OrcaSlicer"', new='"X"', count=2), self.patch(old='"X")\nset(SLIC3R_APP_KEY', new="K", count=1)]
        textpatch.apply(self.root, rows)
        self.assertEqual(read(self.root, "version.inc"), b'set(SLIC3R_APP_NAME K "X")\n')

    def test_refuses_missing_files(self) -> None:
        with self.assertRaises(branding.BrandingError):
            textpatch.apply(self.root, [self.patch(file="absent.txt", count=1)])

    def test_crlf_file_patches_like_lf_and_stays_crlf(self) -> None:
        # A Windows checkout (core.autocrlf) has CRLF files: a row spanning a
        # line break matches on LF text, and the file keeps CRLF throughout.
        lf = read(self.root, "version.inc")
        write(self.root, "version.inc", lf.replace(b"\n", b"\r\n"))
        rows = [self.patch(old='"OrcaSlicer"', new='"X"', count=2), self.patch(old='"X")\nset(SLIC3R_APP_KEY', new="K\nY", count=1)]
        self.assertEqual(textpatch.mismatches(self.root, rows), [])
        textpatch.apply(self.root, rows)
        self.assertEqual(read(self.root, "version.inc"), b'set(SLIC3R_APP_NAME K\r\nY "X")\r\n')

    def test_mixed_file_is_written_with_its_dominant_line_ending(self) -> None:
        write(self.root, "mixed.txt", b"OrcaSlicer\r\nb\r\nc\n")
        textpatch.apply(self.root, [self.patch(file="mixed.txt", old="OrcaSlicer", new="A", count=1)])
        self.assertEqual(read(self.root, "mixed.txt"), b"A\r\nb\r\nc\r\n")

    def test_rejects_malformed_rows(self) -> None:
        bad = [
            {"file": "a", "old": "x", "new": "y", "count": 0, "reason": "r"},
            {"file": "a", "old": "x", "new": "y", "count": True, "reason": "r"},
            {"file": "a", "old": "", "new": "y", "count": 1, "reason": "r"},
            {"file": "a", "old": "x", "new": "y", "count": 1, "reason": " "},
            {"file": "../a", "old": "x", "new": "y", "count": 1, "reason": "r"},
            {"file": "a", "old": "x", "count": 1, "reason": "r"},
            "not a row",
        ]
        for row in bad:
            with self.subTest(row=row):
                with self.assertRaises(branding.BrandingError):
                    textpatch.normalise(row)


if __name__ == "__main__":
    unittest.main()
