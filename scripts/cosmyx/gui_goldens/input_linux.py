"""Keyboard and pointer input on Linux (xdotool, in the Docker image)."""

from __future__ import annotations

import subprocess


def escape(run=subprocess.run) -> None:
    run(["xdotool", "key", "Escape"], check=False)


def park_pointer(run=subprocess.run) -> None:
    run(["xdotool", "mousemove", "0", "0"], check=False)
