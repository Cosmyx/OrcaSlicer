"""Breaker tests for gui_goldens/protocol.py: events of the wrong JSON shape
must raise GoldenError (which the harness reports), never another exception."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_gui_goldens_protocol import GoldenError, capture, protocol  # noqa: E402


class EventShapeTests(unittest.TestCase):
    def test_a_line_that_is_not_an_object_is_a_golden_error(self) -> None:
        """Expected: GoldenError for a valid JSON line that is not an object
        (`[]`, `3`, `"x"`). Actual: validate() calls `.get` on it and
        AttributeError escapes EventReader.poll()."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / protocol.EVENTS).write_bytes(b"[]\n")
            with self.assertRaises(GoldenError):
                protocol.EventReader(Path(tmp)).poll()

    def test_masks_that_are_not_a_list_are_a_golden_error(self) -> None:
        """Expected: GoldenError("bad rectangle") for masks given as an object or
        a string. Actual: `event["masks"] + event["webviews"]` raises TypeError."""
        with self.assertRaises(GoldenError):
            protocol.validate({**capture(2, "x"), "masks": {"x": 1}})

    def test_seq_must_not_be_a_boolean(self) -> None:
        """Expected: GoldenError for "seq": true (bool is not a sequence
        number). Actual: isinstance(True, int) holds and the event is taken
        as seq 1."""
        with self.assertRaises(GoldenError):
            protocol.validate({**capture(1, "x"), "seq": True})


if __name__ == "__main__":
    unittest.main()
