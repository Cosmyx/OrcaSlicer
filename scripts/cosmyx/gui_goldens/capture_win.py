"""Screen capture on Windows runners (decision 0165, OS exception).

GDI BitBlt of the screen area, in physical pixels (the process is made
per-monitor DPI aware first); a popup menu is the visible window of class
"#32768".
"""

from __future__ import annotations

import ctypes
import sys

from . import GoldenError
from .png import Image, from_bgra

SRCCOPY = 0x00CC0020
CAPTUREBLT = 0x40000000


def _api():
    if sys.platform != "win32":
        raise GoldenError("capture_win needs Windows")
    from ctypes import wintypes  # noqa: F401 (Windows only)
    user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
    try:
        user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # PER_MONITOR_AWARE_V2
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()
    return user32, gdi32


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32), ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]


def capture_rect(rect: list[int]) -> Image:
    user32, gdi32 = _api()
    x, y, w, h = rect
    screen = user32.GetDC(None)
    memory = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, w, h)
    old = gdi32.SelectObject(memory, bitmap)
    try:
        if not gdi32.BitBlt(memory, 0, 0, w, h, screen, x, y, SRCCOPY | CAPTUREBLT):
            raise GoldenError("BitBlt failed")
        header = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buffer = ctypes.create_string_buffer(w * h * 4)
        if gdi32.GetDIBits(memory, bitmap, 0, h, buffer, ctypes.byref(header), 0) != h:
            raise GoldenError("GetDIBits failed")
        return from_bgra(w, h, buffer.raw)
    finally:
        gdi32.SelectObject(memory, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory)
        user32.ReleaseDC(None, screen)


def popup_rect() -> list[int] | None:
    user32, _ = _api()
    found: list[list[int]] = []

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    def visit(hwnd, _):
        name = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(ctypes.c_void_p(hwnd), name, 64)
        if name.value == "#32768" and user32.IsWindowVisible(ctypes.c_void_p(hwnd)):
            r = RECT()
            user32.GetWindowRect(ctypes.c_void_p(hwnd), ctypes.byref(r))
            found.append([r.left, r.top, r.right - r.left, r.bottom - r.top])
        return True

    user32.EnumWindows(visit, None)
    # EnumWindows goes top to bottom: the first one is the topmost menu.
    return found[0] if found else None


def capture_popup() -> Image:
    rect = popup_rect()
    if rect is None:
        raise GoldenError("no popup menu on screen")
    return capture_rect(rect)


def capture_menubar(label: str, process: str) -> Image:
    raise GoldenError("Windows has no native menu bar here: menus are popups of the top bar")
