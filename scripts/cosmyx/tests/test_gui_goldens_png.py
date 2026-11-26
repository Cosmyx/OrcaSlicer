"""png and masks: canonical bytes, decoding of other writers' files, masks."""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gui_goldens import GoldenError, masks  # noqa: E402
from gui_goldens import png  # noqa: E402


def checker(width: int = 5, height: int = 3) -> png.Image:
    data = bytearray()
    for y in range(height):
        for x in range(width):
            data += bytes((x * 40 % 256, y * 80 % 256, (x + y) * 30 % 256, 255 if (x + y) % 2 else 128))
    return png.Image(width, height, bytes(data))


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def raw_png(width: int, height: int, colour: int, rows: list[bytes], palette: bytes = b"", depth: int = 8) -> bytes:
    header = struct.pack(">IIBBBBB", width, height, depth, colour, 0, 0, 0)
    body = chunk(b"IHDR", header) + (chunk(b"PLTE", palette) if palette else b"")
    return png.SIGNATURE + body + chunk(b"IDAT", zlib.compress(b"".join(rows))) + chunk(b"IEND", b"")


class CanonicalTests(unittest.TestCase):
    def test_round_trip_keeps_every_pixel(self) -> None:
        image = checker()
        self.assertEqual(png.decode(png.encode(image)), image)

    def test_same_pixels_give_the_same_bytes(self) -> None:
        self.assertEqual(png.encode(checker()), png.encode(checker()))

    def test_only_the_three_required_chunks_are_written(self) -> None:
        blob = png.encode(checker())
        kinds, pos = [], 8
        while pos < len(blob):
            length, kind = struct.unpack(">I4s", blob[pos:pos + 8])
            kinds.append(kind)
            pos += 12 + length
        self.assertEqual(kinds, [b"IHDR", b"IDAT", b"IEND"])
        self.assertEqual(blob[24:26], b"\x08\x06")  # 8-bit RGBA

    def test_write_replaces_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "sub" / "a.png"
            png.write(target, checker())
            png.write(target, checker(2, 2))
            self.assertEqual(png.read(target).width, 2)
            self.assertEqual(sorted(p.name for p in target.parent.iterdir()), ["a.png"])

    def test_bad_buffers_are_refused(self) -> None:
        with self.assertRaises(GoldenError):
            png.Image(2, 2, b"\x00" * 15)
        with self.assertRaises(GoldenError):
            png.decode(b"GIF89a")


class DecodeTests(unittest.TestCase):
    def test_rgb_with_every_filter(self) -> None:
        # Filter bytes 0-4 on successive rows of a 2x5 RGB image.
        rows = [bytes((f,)) + bytes((10, 20, 30, 40, 50, 60)) for f in range(5)]
        image = png.decode(raw_png(2, 5, 2, rows))
        self.assertEqual(image.pixel(0, 0), (10, 20, 30, 255))
        self.assertEqual(image.pixel(1, 0), (40, 50, 60, 255))
        # Row 1, Sub: second pixel adds the first.
        self.assertEqual(image.pixel(1, 1), (50, 70, 90, 255))
        # Row 2, Up: adds row 1.
        self.assertEqual(image.pixel(0, 2), (20, 40, 60, 255))

    def test_gray_palette_and_16_bit(self) -> None:
        gray = png.decode(raw_png(2, 1, 0, [b"\x00\x07\x09"]))
        self.assertEqual(gray.pixel(1, 0), (9, 9, 9, 255))
        indexed = png.decode(raw_png(2, 1, 3, [b"\x00\x01\x00"], palette=bytes((1, 2, 3, 4, 5, 6))))
        self.assertEqual(indexed.pixel(0, 0), (4, 5, 6, 255))
        deep = png.decode(raw_png(1, 1, 6, [b"\x00" + bytes((1, 0, 2, 0, 3, 0, 4, 0))], depth=16))
        self.assertEqual(deep.pixel(0, 0), (1, 2, 3, 4))

    def test_interlaced_files_are_refused(self) -> None:
        blob = bytearray(raw_png(1, 1, 6, [b"\x00\x00\x00\x00\x00"]))
        blob[28] = 1  # interlace byte of IHDR
        with self.assertRaises(GoldenError):
            png.decode(bytes(blob))


class BufferTests(unittest.TestCase):
    def test_bgra_rows_become_rgba(self) -> None:
        data = bytes((3, 2, 1, 0, 6, 5, 4, 0)) + bytes(8)  # stride 16 for a 2-pixel row
        image = png.from_bgra(2, 1, data, stride=16)
        self.assertEqual(image.pixel(0, 0), (1, 2, 3, 255))
        self.assertEqual(image.pixel(1, 0), (4, 5, 6, 255))

    def test_bottom_up_rows_are_flipped(self) -> None:
        data = bytes((0, 0, 1, 0)) + bytes((0, 0, 2, 0))
        image = png.from_bgra(1, 2, data, bottom_up=True)
        self.assertEqual(image.pixel(0, 0), (2, 0, 0, 255))

    def test_crop_and_its_bounds(self) -> None:
        image = checker()
        self.assertEqual(image.crop(1, 1, 2, 2).pixel(0, 0), image.pixel(1, 1))
        with self.assertRaises(GoldenError):
            image.crop(4, 0, 2, 1)


class MaskTests(unittest.TestCase):
    def test_masks_paint_magenta_and_clip(self) -> None:
        image = masks.apply(checker(), [[3, 1, 10, 10], [-5, -5, 1, 1]])
        self.assertEqual(image.pixel(4, 2), (255, 0, 255, 255))
        self.assertEqual(image.pixel(3, 1), (255, 0, 255, 255))
        self.assertEqual(image.pixel(2, 1), checker().pixel(2, 1))
        self.assertEqual(image.pixel(0, 0), checker().pixel(0, 0))


if __name__ == "__main__":
    unittest.main()
