"""Minimal, deterministic Windows ICO writer and structural parser.

The layout follows the upstream OrcaSlicer.ico: entries in ascending size, 32-bit BMP (DIB) payloads below
256 px for the widest compatibility (resource compiler, NSIS, old shells), and a PNG payload at 256 px, as
Windows Vista and later expect. No timestamp or variable field: the same PNG renders give the same bytes.
"""

from __future__ import annotations

import struct
from collections.abc import Mapping

from . import raster

HEADER = struct.Struct("<HHH")
ENTRY = struct.Struct("<BBBBHHII")
DIB_HEADER = struct.Struct("<IiiHHIIiiII")
PNG_FROM = 256


def _dib(image: raster.Image) -> bytes:
    """32-bit BGRA bottom-up DIB with its AND mask (set where the pixel is fully transparent)."""
    width, height = image.width, image.height
    mask_stride = ((width + 31) // 32) * 4
    colour = bytearray()
    mask = bytearray()
    for y in reversed(range(height)):
        row = image.rgba[y * width * 4 : (y + 1) * width * 4]
        bits = bytearray(mask_stride)
        for x in range(width):
            red, green, blue, alpha = row[4 * x : 4 * x + 4]
            colour += bytes((blue, green, red, alpha))
            if alpha == 0:
                bits[x // 8] |= 0x80 >> (x % 8)
        mask += bits
    header = DIB_HEADER.pack(DIB_HEADER.size, width, height * 2, 1, 32, 0, len(colour) + len(mask), 0, 0, 0, 0)
    return header + bytes(colour) + bytes(mask)


def write_ico(pngs: Mapping[int, bytes]) -> bytes:
    """ICO bytes from square PNG renders keyed by pixel size (1 to 256)."""
    if not pngs:
        raise ValueError("an ICO needs at least one size")
    payloads = []
    for size in sorted(pngs):
        if not 1 <= size <= 256:
            raise ValueError(f"ICO sizes go from 1 to 256 px, not {size}")
        if raster.png_size(pngs[size]) != (size, size):
            raise ValueError(f"{size} px payload is not a {size}x{size} PNG")
        payloads.append((size, pngs[size] if size >= PNG_FROM else _dib(raster.decode(pngs[size]))))
    offset = HEADER.size + ENTRY.size * len(payloads)
    entries = b""
    for size, payload in payloads:
        byte = 0 if size == 256 else size
        entries += ENTRY.pack(byte, byte, 0, 0, 1, 32, len(payload), offset)
        offset += len(payload)
    return HEADER.pack(0, 1, len(payloads)) + entries + b"".join(payload for _, payload in payloads)


def parse_ico(data: bytes) -> list[tuple[int, str, bytes]]:
    """Entries of an ICO file as (pixel size, "png" or "bmp", payload); ValueError when the structure is broken."""
    if len(data) < HEADER.size:
        raise ValueError("too short for an ICO header")
    reserved, kind, count = HEADER.unpack_from(data, 0)
    if reserved != 0 or kind != 1 or count == 0:
        raise ValueError("not an ICO file")
    result = []
    for index in range(count):
        start = HEADER.size + ENTRY.size * index
        if start + ENTRY.size > len(data):
            raise ValueError("truncated ICO directory")
        width, _, _, _, _, _, length, offset = ENTRY.unpack_from(data, start)
        payload = data[offset : offset + length]
        if len(payload) != length:
            raise ValueError(f"entry {index} runs past the end of the file")
        result.append((width or 256, "png" if payload.startswith(raster.PNG_SIGNATURE) else "bmp", payload))
    return result
