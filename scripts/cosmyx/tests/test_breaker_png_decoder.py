"""Breaker tests for gui_goldens/png.py decode: damaged files must raise
GoldenError (the error the harness turns into a failed surface), never another
exception."""

from __future__ import annotations

import struct
import sys
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gui_goldens import GoldenError, png  # noqa: E402


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def ihdr(width: int, height: int, depth: int, colour: int) -> bytes:
    return chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, colour, 0, 0, 0))


def rgba_image() -> bytes:
    return png.encode(png.Image(2, 2, bytes(range(16))))


class DamagedPngTests(unittest.TestCase):
    def test_truncated_idat_raises_golden_error(self) -> None:
        """Expected: GoldenError. Actual: zlib.error (incomplete stream) escapes."""
        blob = png.SIGNATURE + ihdr(4, 4, 8, 6) + chunk(b"IDAT", zlib.compress(b"\x00" * 17 * 4)[:6]) + \
            chunk(b"IEND", b"")
        with self.assertRaises(GoldenError):
            png.decode(blob)

    def test_short_pixel_data_raises_golden_error(self) -> None:
        """Expected: GoldenError when the inflated data holds fewer rows than
        IHDR says. Actual: IndexError from _unfilter."""
        blob = png.SIGNATURE + ihdr(4, 4, 8, 6) + chunk(b"IDAT", zlib.compress(b"\x00" * 17)) + chunk(b"IEND", b"")
        with self.assertRaises(GoldenError):
            png.decode(blob)

    def test_palette_image_without_plte_raises_golden_error(self) -> None:
        """Expected: GoldenError for a palette image with no PLTE chunk (or an
        index past the palette). Actual: the empty palette slice shrinks the
        output buffer and IndexError escapes."""
        blob = png.SIGNATURE + ihdr(1, 1, 8, 3) + chunk(b"IDAT", zlib.compress(b"\x00\x05")) + chunk(b"IEND", b"")
        with self.assertRaises(GoldenError):
            png.decode(blob)

    def test_bad_ihdr_length_raises_golden_error(self) -> None:
        """Expected: GoldenError. Actual: struct.error from unpacking a short IHDR."""
        blob = png.SIGNATURE + chunk(b"IHDR", b"\x00\x00\x00\x01") + chunk(b"IEND", b"")
        with self.assertRaises(GoldenError):
            png.decode(blob)


if __name__ == "__main__":
    unittest.main()
