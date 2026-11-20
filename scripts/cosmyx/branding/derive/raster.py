"""Minimal, deterministic PNG decoder and encoder for the derived branding rasters.

Only what resvg writes is read: 8-bit RGB or RGBA, non-interlaced. The encoder always writes 8-bit RGBA with
filter 0 and zlib level 9, and no ancillary chunk (no time, no gamma, no text), so the same pixels give the
same bytes in the pinned image.
"""

from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {2: 3, 6: 4}


@dataclass(frozen=True)
class Image:
    """Straight (not premultiplied) RGBA pixels, row by row, 4 bytes per pixel."""

    width: int
    height: int
    rgba: bytes


def _chunks(data: bytes):
    if not data.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG")
    offset = len(PNG_SIGNATURE)
    while offset + 8 <= len(data):
        (length,) = struct.unpack(">I", data[offset : offset + 4])
        kind = data[offset + 4 : offset + 8]
        body = data[offset + 8 : offset + 8 + length]
        if len(body) != length:
            raise ValueError(f"truncated {kind!r} chunk")
        yield kind, body
        offset += 12 + length
        if kind == b"IEND":
            return
    raise ValueError("PNG has no IEND chunk")


def _paeth(left: int, up: int, corner: int) -> int:
    estimate = left + up - corner
    da, db, dc = abs(estimate - left), abs(estimate - up), abs(estimate - corner)
    if da <= db and da <= dc:
        return left
    return up if db <= dc else corner


def _unfilter(raw: bytes, width: int, height: int, bpp: int) -> bytes:
    stride = width * bpp
    out = bytearray()
    previous = bytearray(stride)
    position = 0
    for _ in range(height):
        kind = raw[position]
        line = bytearray(raw[position + 1 : position + 1 + stride])
        position += 1 + stride
        if len(line) != stride:
            raise ValueError("truncated image data")
        for i in range(stride):
            left = line[i - bpp] if i >= bpp else 0
            up = previous[i]
            corner = previous[i - bpp] if i >= bpp else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + ((left + up) >> 1)) & 0xFF
            elif kind == 4:
                line[i] = (line[i] + _paeth(left, up, corner)) & 0xFF
            elif kind != 0:
                raise ValueError(f"unknown PNG filter {kind}")
        out += line
        previous = line
    return bytes(out)


def decode(data: bytes) -> Image:
    """RGBA pixels of an 8-bit RGB or RGBA, non-interlaced PNG; ValueError for anything else."""
    header = None
    idat = bytearray()
    for kind, body in _chunks(data):
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
    if header is None:
        raise ValueError("PNG has no IHDR chunk")
    width, height, depth, colour, _, _, interlace = header
    if depth != 8 or colour not in CHANNELS or interlace != 0:
        raise ValueError(f"unsupported PNG (depth {depth}, colour type {colour}, interlace {interlace})")
    bpp = CHANNELS[colour]
    pixels = _unfilter(zlib.decompress(bytes(idat)), width, height, bpp)
    if bpp == 3:
        rgba = bytearray()
        for i in range(0, len(pixels), 3):
            rgba += pixels[i : i + 3] + b"\xff"
        pixels = bytes(rgba)
    return Image(width, height, pixels)


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def encode(image: Image) -> bytes:
    """8-bit RGBA PNG bytes of `image`, filter 0, zlib level 9."""
    stride = image.width * 4
    if len(image.rgba) != stride * image.height:
        raise ValueError("pixel buffer does not match the image size")
    raw = b"".join(b"\x00" + image.rgba[y * stride : (y + 1) * stride] for y in range(image.height))
    header = struct.pack(">IIBBBBB", image.width, image.height, 8, 6, 0, 0, 0)
    return PNG_SIGNATURE + _chunk(b"IHDR", header) + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")


def luma(red: int, green: int, blue: int) -> int:
    """ITU-R BT.601 luma, rounded, in integer arithmetic (the same result on every host)."""
    return (299 * red + 587 * green + 114 * blue + 500) // 1000


def grayscale(image: Image) -> Image:
    """The same image with every pixel set to its luma; alpha is kept."""
    out = bytearray(image.rgba)
    for i in range(0, len(out), 4):
        value = luma(out[i], out[i + 1], out[i + 2])
        out[i] = out[i + 1] = out[i + 2] = value
    return Image(image.width, image.height, bytes(out))


def png_size(data: bytes) -> tuple[int, int]:
    """(width, height) read from a PNG's IHDR chunk; ValueError when the bytes are not a PNG."""
    if len(data) < 24 or not data.startswith(PNG_SIGNATURE) or data[12:16] != b"IHDR":
        raise ValueError("payload is not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    return width, height
