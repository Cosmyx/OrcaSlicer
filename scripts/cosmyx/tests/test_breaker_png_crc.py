"""Breaker test for gui_goldens/png.py decode: chunk CRCs."""

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


class ChunkCrcTests(unittest.TestCase):
    def test_crc_error_is_detected(self) -> None:
        """Expected: GoldenError for a chunk whose CRC does not match (a golden
        damaged in transit or by a bad merge must not be compared as if it were
        intact). Actual: CRCs are never checked: a PNG whose IHDR CRC is wrong decodes
        as if nothing happened."""
        blob = bytearray(rgba_image())
        ihdr_crc = len(png.SIGNATURE) + 8 + 13  # length, type, 13 data bytes, then the CRC
        blob[ihdr_crc] ^= 0xFF
        with self.assertRaises(GoldenError):
            png.decode(bytes(blob))


if __name__ == "__main__":
    unittest.main()
