"""Breaker tests of the branding engine (T11a): text patches, the overlay,
the manifest and the apply / revert pipeline.

Every test here reproduces one hole and fails until the engine is fixed.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from branding_fixture import TreeCase, apply_module, branding, guards, manifest, read, snapshot, textpatch, write

PN = branding.PRODUCT_NAME_DIR


def can_symlink() -> bool:
    with tempfile.TemporaryDirectory() as folder:
        try:
            os.symlink(folder, Path(folder) / "probe")
        except (OSError, NotImplementedError):
            return False
    return True


def case_insensitive(folder: Path) -> bool:
    probe = folder / "CaseProbe"
    probe.write_bytes(b"")
    try:
        return (folder / "caseprobe").exists()
    finally:
        probe.unlink()


class TextPatchPathTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.root = self.base / "repo"
        self.root.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @unittest.skipUnless(can_symlink(), "symlinks unavailable on this host")
    def test_symlink_does_not_escape_the_tree(self) -> None:
        """A patched path that is a symlink to a file outside the repository:
        the patch writes through it and edits a file outside the tree."""
        outside = self.base / "outside.txt"
        outside.write_text("OrcaSlicer\n")
        (self.root / "link.txt").symlink_to(outside)
        try:
            textpatch.apply(self.root, [textpatch.Patch("link.txt", "OrcaSlicer", "CosmoSlice", 1, "r")])
        except branding.BrandingError:
            pass
        self.assertEqual(outside.read_text(), "OrcaSlicer\n")

    def test_case_only_path_difference_is_refused(self) -> None:
        """Row file `src/file.txt`, tree file `src/File.txt`: Linux refuses
        the row (cannot read), a case-insensitive macOS or Windows disk
        patches the file. A row must match the tracked spelling on every OS.
        (On a case-sensitive disk this already holds.)"""
        write(self.root, "src/File.txt", "OrcaSlicer\n")
        if not case_insensitive(self.root / "src"):
            self.skipTest("case-sensitive file system: the row is already refused")
        with self.assertRaises(branding.BrandingError):
            textpatch.apply(self.root, [textpatch.Patch("src/file.txt", "OrcaSlicer", "CosmoSlice", 1, "r")])


class OverlaySymlinkTest(TreeCase):
    @unittest.skipUnless(can_symlink(), "symlinks unavailable on this host")
    def test_symlinked_overlay_file_is_an_error(self) -> None:
        """An overlay file committed as a symlink: git checks it out as a
        text file holding the target path on Windows, so its hash differs by
        OS, and on macOS / Linux apply copies whatever it points at. The
        guards must reject it instead of syncing and applying it."""
        target = self.root / "elsewhere.svg"
        target.write_text(read(self.root, "resources/images/apple.svg").decode("utf-8").replace("#009688", "#8000FF"))
        link = self.root.joinpath(*f"{branding.OVERLAY_DIR}/resources/images/apple.svg".split("/"))
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(target)
        self.sync()
        found = [f for f in self.findings("pre") if f.level == "error" and f.path == "resources/images/apple.svg"]
        self.assertTrue(found, "no error for a symlinked overlay file")


class ManifestCaseTest(TreeCase):
    def test_case_only_duplicate_rows_are_invalid(self) -> None:
        """Two rows whose paths differ only by case name one file on macOS
        and Windows: validate must reject them like an exact duplicate."""
        rows = manifest.load(self.root).groups["icons-a-m"]
        apple = next(row for row in rows if row["path"] == "resources/images/apple.svg")
        rows.append(dict(apple, path="resources/images/Apple.svg"))
        manifest.save(self.root, manifest.load(self.root).__class__({**manifest.load(self.root).groups, "icons-a-m": rows}))
        problems = manifest.validate(self.root)
        self.assertTrue(any("Apple.svg" in problem for problem in problems), problems)


class PipelineFailureTest(TreeCase):
    use_git = False

    def setUp(self) -> None:
        super().setUp()
        self.write_json(
            f"{PN}/patches.json",
            {
                "schema": 1,
                "rows": [
                    {"file": "README.md", "old": "OrcaSlicer", "new": "CosmoSlice", "count": 1, "reason": "t"},
                    {
                        "file": "version.inc",
                        "old": 'SLIC3R_APP_NAME "OrcaSlicer"',
                        "new": 'SLIC3R_APP_NAME "CosmoSlice"',
                        "count": 1,
                        "reason": "t",
                    },
                ],
            },
        )
        self.original = snapshot(self.root)

    def test_unexpected_stage_error_reverts(self) -> None:
        """A stage that fails with anything but BrandingError / OSError (a
        plugin bug: KeyError, ValueError, UnicodeError) escapes apply(): the
        files already written stay branded and no report is written."""

        class Buggy:
            @staticmethod
            def apply(ctx, backup):
                return {}["missing key"]

            @staticmethod
            def guards(ctx, phase):
                return []

        try:
            code, _ = self.apply(plugins={"product_name": [Buggy]})
        except KeyError:
            code = None
        self.assertEqual(code, 1)
        self.assertEqual(snapshot(self.root), self.original)

    def test_interrupted_revert_can_be_resumed(self) -> None:
        """revert restores and deletes each backup one by one, and drops
        state.json only at the end. Interrupted after the first file, the
        state still lists a file whose backup is gone, so every later
        revert (or apply) fails with FileNotFoundError."""
        code, lines = self.apply()
        self.assertEqual(code, 0, lines)
        real_copy = shutil.copy2
        calls = []

        def flaky(source, destination, *args, **kwargs):
            calls.append(source)
            if len(calls) == 2:
                raise OSError("disk went away")
            return real_copy(source, destination, *args, **kwargs)

        with mock.patch.object(apply_module.shutil, "copy2", flaky):
            with self.assertRaises(OSError):
                apply_module.revert(self.root)
        apply_module.revert(self.root)
        self.assertEqual(snapshot(self.root), self.original)


class ColourTableCrashTest(TreeCase):
    def test_bad_allow_residue_count_is_a_finding(self) -> None:
        """An allow_residue row with a non-numeric count: the guards crash
        with ValueError (int("two")) instead of reporting a G5/G6 error."""
        self.write_json(
            branding.COLOURS_FILE,
            {
                "schema": 1,
                "literals": [],
                "allow_residue": [{"file": "README.md", "match": "#009688", "count": "two", "reason": "t"}],
            },
        )
        try:
            found = self.findings("pre")
        except ValueError as error:
            self.fail(f"guards raised {error!r}")
        self.assertTrue(any(f.level == "error" and f.guard in ("G5", "G6") for f in found), found)


if __name__ == "__main__":
    unittest.main()
