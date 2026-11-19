"""Keyboard input on macOS runners (System Events)."""

from __future__ import annotations

import subprocess


def escape(run=subprocess.run) -> None:
    run(["osascript", "-e", 'tell application "System Events" to key code 53'], check=False)


def park_pointer(run=subprocess.run) -> None:
    # macOS has no stock tool to move the pointer; the runner starts with it
    # parked in a corner.
    return None
