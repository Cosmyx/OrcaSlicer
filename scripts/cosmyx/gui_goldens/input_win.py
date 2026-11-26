"""Keyboard and pointer input on Windows runners (user32 through ctypes)."""

from __future__ import annotations

import ctypes
import sys

VK_ESCAPE = 0x1B
KEYEVENTF_KEYUP = 0x0002


def escape() -> None:
    if sys.platform != "win32":
        return
    user32 = ctypes.windll.user32
    user32.keybd_event(VK_ESCAPE, 0, 0, 0)
    user32.keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, 0)


def park_pointer() -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.SetCursorPos(0, 0)
