"""Canonical PNG files: 8-bit RGBA, no metadata, filter 0, zlib level 9
(decision 0171).

Two captures with the same pixels give the same bytes, so the Linux goldens
can be compared byte for byte and git stores one blob per distinct image. The
decoder reads the PNG files the macOS screencapture tool writes too (8-bit
gray, RGB, RGBA, palette; 16-bit is reduced to 8-bit).
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from . import GoldenError

SIGNATURE = b"\x89PNG\r\n\x1a\n"


@dataclass
class Image:
    """Pixels as RGBA bytes, row after row, four bytes per pixel."""

    width: int
    height: int
    rgba: bytes

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0 or len(self.rgba) != self.width * self.height * 4:
            raise GoldenError(f"bad image buffer: {self.width}x{self.height}, {len(self.rgba)} bytes")

    def pixel(self, x: int, y: int) -> tuple[int, int, int, int]:
        i = (y * self.width + x) * 4
        return tuple(self.rgba[i:i + 4])  # type: ignore[return-value]

    def crop(self, x: int, y: int, w: int, h: int) -> "Image":
        if x < 0 or y < 0 or w <= 0 or h <= 0 or x + w > self.width or y + h > self.height:
            raise GoldenError(f"crop {x},{y} {w}x{h} is outside the {self.width}x{self.height} image")
        rows = bytearray()
        for row in range(y, y + h):
            start = (row * self.width + x) * 4
            rows += self.rgba[start:start + w * 4]
        return Image(w, h, bytes(rows))


def from_bgra(width: int, height: int, data: bytes, stride: int | None = None, bottom_up: bool = False) -> Image:
    """Image from 32-bit BGRA/BGRX rows (Windows DIB, X11 ZPixmap); alpha forced to 255."""
    stride = stride or width * 4
    out = bytearray(width * height * 4)
    for row in range(height):
        src_row = (height - 1 - row) if bottom_up else row
        src = data[src_row * stride:src_row * stride + width * 4]
        dst = row * width * 4
        out[dst + 0:dst + width * 4:4] = src[2::4]
        out[dst + 1:dst + width * 4:4] = src[1::4]
        out[dst + 2:dst + width * 4:4] = src[0::4]
        out[dst + 3:dst + width * 4:4] = b"\xff" * width
    return Image(width, height, bytes(out))


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode(image: Image) -> bytes:
    stride = image.width * 4
    raw = bytearray()
    for row in range(image.height):
        raw += b"\x00" + image.rgba[row * stride:(row + 1) * stride]
    header = struct.pack(">IIBBBBB", image.width, image.height, 8, 6, 0, 0, 0)
    compressor = zlib.compressobj(9, zlib.DEFLATED, 15, 9, zlib.Z_DEFAULT_STRATEGY)
    data = compressor.compress(bytes(raw)) + compressor.flush()
    return SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", data) + _chunk(b"IEND", b"")


def write(path: Path, image: Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_bytes(encode(image))
    temp.replace(path)


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _unfilter(data: bytes, width: int, height: int, bpp: int) -> bytes:
    stride = width * bpp
    out = bytearray(height * stride)
    previous = bytearray(stride)
    pos = 0
    for row in range(height):
        kind = data[pos]
        line = bytearray(data[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if kind == 1:
            for i in range(bpp, stride):
                line[i] = (line[i] + line[i - bpp]) & 0xFF
        elif kind == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif kind == 3:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif kind == 4:
            for i in range(stride):
                left = line[i - bpp] if i >= bpp else 0
                up_left = previous[i - bpp] if i >= bpp else 0
                line[i] = (line[i] + _paeth(left, previous[i], up_left)) & 0xFF
        elif kind != 0:
            raise GoldenError(f"unknown PNG filter {kind}")
        out[row * stride:(row + 1) * stride] = line
        previous = line
    return bytes(out)


def decode(blob: bytes) -> Image:
    if not blob.startswith(SIGNATURE):
        raise GoldenError("not a PNG file")
    pos, idat, palette, header = len(SIGNATURE), bytearray(), b"", None
    while pos + 8 <= len(blob):
        length, kind = struct.unpack(">I4s", blob[pos:pos + 8])
        data = blob[pos + 8:pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", data)
        elif kind == b"PLTE":
            palette = data
        elif kind == b"IDAT":
            idat += data
        elif kind == b"IEND":
            break
    if header is None:
        raise GoldenError("PNG without IHDR")
    width, height, depth, colour, _, _, interlace = header
    if interlace:
        raise GoldenError("interlaced PNG files are not supported")
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(colour)
    if channels is None or depth not in (8, 16) or (colour == 3 and depth != 8):
        raise GoldenError(f"unsupported PNG: colour type {colour}, depth {depth}")
    bpp = channels * depth // 8
    pixels = _unfilter(zlib.decompress(bytes(idat)), width, height, bpp)
    if depth == 16:
        pixels = pixels[0::2]
    out = bytearray(width * height * 4)
    if colour == 6:
        out[:] = pixels
    elif colour == 2:
        out[0::4], out[1::4], out[2::4] = pixels[0::3], pixels[1::3], pixels[2::3]
        out[3::4] = b"\xff" * (width * height)
    elif colour == 0:
        out[0::4] = out[1::4] = out[2::4] = pixels
        out[3::4] = b"\xff" * (width * height)
    elif colour == 4:
        out[0::4] = out[1::4] = out[2::4] = pixels[0::2]
        out[3::4] = pixels[1::2]
    else:
        for i, index in enumerate(pixels):
            out[i * 4:i * 4 + 3] = palette[index * 3:index * 3 + 3]
            out[i * 4 + 3] = 255
    return Image(width, height, bytes(out))


def read(path: Path) -> Image:
    return decode(path.read_bytes())
