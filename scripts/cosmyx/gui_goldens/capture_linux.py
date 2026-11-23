"""Screen capture on Linux, under Xvfb in the pinned Docker image (decision
0165, OS exception: one capture backend per OS behind capture_for()).

The root window is dumped with xwd and cropped; a popup menu is the topmost
viewable override-redirect child of the root window (GTK menus are
override-redirect), found with xwininfo.
"""

from __future__ import annotations

import re
import struct
import subprocess
from collections.abc import Callable

from . import GoldenError
from .png import Image, from_bgra

Runner = Callable[..., subprocess.CompletedProcess]
CHILD = re.compile(r"^\s+(0x[0-9a-f]+) .*?\s(\d+)x(\d+)\+(-?\d+)\+(-?\d+)\s+\+(-?\d+)\+(-?\d+)\s*$")


def parse_xwd(blob: bytes) -> Image:
    """Image of an xwd dump (ZPixmap, 24 or 32 bits per pixel)."""
    if len(blob) < 100:
        raise GoldenError("xwd dump too short")
    fields = struct.unpack(">25I", blob[:100])
    header_size, _, pixmap_format, _, width, height = fields[:6]
    byte_order, bits_per_pixel, bytes_per_line, ncolors = fields[7], fields[11], fields[12], fields[19]
    if pixmap_format != 2 or bits_per_pixel != 32:
        raise GoldenError(f"unsupported xwd dump: format {pixmap_format}, {bits_per_pixel} bits per pixel")
    start = header_size + ncolors * 12
    data = blob[start:start + bytes_per_line * height]
    if len(data) < bytes_per_line * height:
        raise GoldenError("xwd dump truncated")
    if byte_order == 1:  # MSBFirst: XRGB, swap to BGRX
        swapped = bytearray(data)
        swapped[0::4], swapped[1::4], swapped[2::4], swapped[3::4] = data[3::4], data[2::4], data[1::4], data[0::4]
        data = bytes(swapped)
    return from_bgra(width, height, data, bytes_per_line)


def root_image(run: Runner = subprocess.run) -> Image:
    done = run(["xwd", "-root", "-silent"], capture_output=True, check=False)
    if done.returncode != 0:
        raise GoldenError(f"xwd failed: {done.stderr.decode(errors='replace').strip()}")
    return parse_xwd(done.stdout)


def capture_rect(rect: list[int], run: Runner = subprocess.run) -> Image:
    x, y, w, h = rect
    screen = root_image(run)
    # Windows partly off screen are cropped to the screen.
    x0, y0 = max(0, x), max(0, y)
    w, h = min(w - (x0 - x), screen.width - x0), min(h - (y0 - y), screen.height - y0)
    return screen.crop(x0, y0, w, h)


def popup_rect(run: Runner = subprocess.run) -> list[int] | None:
    done = run(["xwininfo", "-root", "-children"], capture_output=True, text=True, check=False)
    candidates = []
    for line in done.stdout.splitlines():
        match = CHILD.match(line)
        if match:
            wid, w, h = match.group(1), int(match.group(2)), int(match.group(3))
            x, y = int(match.group(6)), int(match.group(7))
            if w > 16 and h > 16:
                candidates.append((wid, [x, y, w, h]))
    # xwininfo lists the children bottom to top: the topmost popup is last.
    for wid, rect in reversed(candidates):
        stats = run(["xwininfo", "-id", wid, "-stats"], capture_output=True, text=True, check=False).stdout
        if "Map State: IsViewable" in stats and "Override Redirect State: yes" in stats:
            return rect
    return None


def capture_popup(run: Runner = subprocess.run) -> Image:
    rect = popup_rect(run)
    if rect is None:
        raise GoldenError("no popup menu on screen")
    return capture_rect(rect, run)


def capture_menubar(label: str, process: str, run: Runner = subprocess.run) -> Image:
    raise GoldenError("Linux has no native menu bar: menus are popups of the top bar")
