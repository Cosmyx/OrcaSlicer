"""One capture interface over the per-OS backends (decision 0165: the OS
exception sits behind this module and nowhere else)."""

from __future__ import annotations

import importlib

from . import GoldenError
from .png import Image

BACKENDS = {"linux": ("capture_linux", "input_linux"), "macos": ("capture_mac", "input_mac"),
            "windows": ("capture_win", "input_win")}


class Capturer:
    def __init__(self, os_name: str, process: str = ""):
        if os_name not in BACKENDS:
            raise GoldenError(f"no capture backend for {os_name!r}")
        capture_name, input_name = BACKENDS[os_name]
        self.os = os_name
        self.process = process
        self.capture = importlib.import_module(f"{__package__}.{capture_name}")
        self.input = importlib.import_module(f"{__package__}.{input_name}")

    def rect(self, rect_px: list[int], scale: float) -> Image:
        if self.os == "macos":
            return self.capture.capture_rect(rect_px, scale)
        return self.capture.capture_rect(rect_px)

    def popup(self) -> Image:
        return self.capture.capture_popup()

    def menubar(self, label: str) -> Image:
        return self.capture.capture_menubar(label, self.process)

    def escape(self) -> None:
        self.input.escape()

    def park_pointer(self) -> None:
        self.input.park_pointer()
