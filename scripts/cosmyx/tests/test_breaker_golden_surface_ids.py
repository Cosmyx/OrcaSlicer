"""Breaker tests for gui_goldens: surface ids become file names of goldens
(protocol.image_file_name, text_file_name, cli.Pass.store)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_gui_goldens_protocol import FakeCapturer, GoldenError, Pass, capture, protocol  # noqa: E402


class SurfaceIdTests(unittest.TestCase):
    def test_ids_that_are_not_safe_file_names_are_rejected(self) -> None:
        """Expected: GoldenError for a capture id that is not a portable file
        name: a path ("../x", "a/b", "a\\\\b"), a Windows reserved name ("CON",
        "nul"), a name with characters Windows forbids ("a:b", "a?b"), or not a
        string. Actual: validate() accepts any id, so "../x" writes x.png
        outside the images folder and "CON" cannot be written on Windows."""
        for bad in ("../x", "a/b", "a\\b", "CON", "nul", "a:b", "a?b", "", 5):
            with self.subTest(id=bad), self.assertRaises(GoldenError):
                protocol.validate(capture(1, bad))

    def test_a_capture_id_cannot_escape_the_images_folder(self) -> None:
        """Expected: storing a capture never writes outside the images folder.
        Actual: Pass.store joins the id to the folder, so id "../escaped"
        writes escaped.png next to it."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images, driver = root / "out" / "images", root / "out" / "driver"
            driver.mkdir(parents=True)
            one = Pass(driver, images, FakeCapturer(), webview_mask=False)
            try:
                one.handle(capture(1, "../escaped"))
            except GoldenError:
                pass
            self.assertFalse((root / "out" / "escaped.png").exists())

    def test_a_duplicate_capture_id_is_reported(self) -> None:
        """Expected: a second capture with an id already captured in the pass is
        a failure (the first state would otherwise be lost). Actual: the second
        image silently overwrites the first and the pass reports no failure."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            images, driver = root / "images", root / "driver"
            driver.mkdir()
            one = Pass(driver, images, FakeCapturer(), webview_mask=False)
            one.handle(capture(1, "10-main"))
            one.handle(capture(2, "10-main", kind="dialog"))
            self.assertTrue(one.fails, "duplicate surface id 10-main not reported")


if __name__ == "__main__":
    unittest.main()
