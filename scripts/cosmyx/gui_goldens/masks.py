"""Masked areas of a capture are painted #FF00FF before the image is stored
(decision 0169), so content the goldens cannot pin (a system WebView) never
reaches a golden or a comparison."""

from __future__ import annotations

from collections.abc import Iterable

from .png import Image

MASK_RGBA = bytes((0xFF, 0x00, 0xFF, 0xFF))


def apply(image: Image, rects: Iterable[Iterable[int]]) -> Image:
    """Paint each [x, y, w, h] rectangle, clipped to the image."""
    data = bytearray(image.rgba)
    for rect in rects:
        x, y, w, h = (int(v) for v in rect)
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(image.width, x + w), min(image.height, y + h)
        if x1 <= x0 or y1 <= y0:
            continue
        row = MASK_RGBA * (x1 - x0)
        for line in range(y0, y1):
            start = (line * image.width + x0) * 4
            data[start:start + len(row)] = row
    return Image(image.width, image.height, bytes(data))
