"""Screen capture on macOS runners (decision 0165, OS exception).

screencapture writes the area in points; the native menu bar is opened with
System Events (the runner image grants osascript Accessibility and Screen
Recording), and a menu window is found with CGWindowListCopyWindowInfo through
JavaScript for Automation, which ships with macOS.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

from . import GoldenError
from . import png as png_mod

Runner = Callable[..., subprocess.CompletedProcess]
MENU_LAYER = 101  # kCGPopUpMenuWindowLevel

WINDOWS_JXA = """
ObjC.import('CoreGraphics');
const list = ObjC.castRefToObject($.CGWindowListCopyWindowInfo($.kCGWindowListOptionOnScreenOnly, 0));
const out = [];
for (let i = 0; i < list.count; i++) {
  const w = list.objectAtIndex(i);
  out.push({owner: ObjC.unwrap(w.objectForKey('kCGWindowOwnerName')),
            layer: ObjC.unwrap(w.objectForKey('kCGWindowLayer')),
            bounds: ObjC.deepUnwrap(w.objectForKey('kCGWindowBounds'))});
}
JSON.stringify(out);
"""


def points(rect_px: list[int], scale: float) -> list[int]:
    scale = scale or 1.0
    return [int(round(v / scale)) for v in rect_px]


def capture_points(rect: list[int], run: Runner = subprocess.run) -> png_mod.Image:
    x, y, w, h = rect
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "capture.png"
        done = run(["screencapture", "-x", "-o", "-t", "png", f"-R{x},{y},{w},{h}", str(target)],
                   capture_output=True, text=True, check=False)
        if done.returncode != 0 or not target.is_file():
            raise GoldenError(f"screencapture failed ({done.returncode}): {done.stderr.strip()}")
        return png_mod.read(target)


def capture_rect(rect: list[int], scale: float = 1.0, run: Runner = subprocess.run) -> png_mod.Image:
    return capture_points(points(rect, scale), run)


def menu_windows(run: Runner = subprocess.run) -> list[list[int]]:
    done = run(["osascript", "-l", "JavaScript", "-e", WINDOWS_JXA], capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise GoldenError(f"window list failed: {done.stderr.strip()}")
    rects = []
    for window in json.loads(done.stdout or "[]"):
        bounds = window.get("bounds") or {}
        if window.get("layer") == MENU_LAYER and bounds.get("Width", 0) > 16 and bounds.get("Height", 0) > 16:
            rects.append([int(bounds["X"]), int(bounds["Y"]), int(bounds["Width"]), int(bounds["Height"])])
    return rects


def wait_menu(run: Runner = subprocess.run, timeout: float = 5.0, sleep=time.sleep) -> list[int]:
    deadline = time.monotonic() + timeout
    while True:
        rects = menu_windows(run)
        if rects:
            return rects[0]
        if time.monotonic() > deadline:
            raise GoldenError("no menu window on screen")
        sleep(0.2)


def capture_popup(run: Runner = subprocess.run) -> png_mod.Image:
    return capture_points(wait_menu(run), run)


def capture_menubar(label: str, process: str, run: Runner = subprocess.run, popen=subprocess.Popen) -> png_mod.Image:
    # "click menu bar item" can block until the menu closes, so it runs in
    # the background while the menu is captured.
    script = (f'tell application "System Events" to tell process "{process}" '
              f'to click menu bar item "{label}" of menu bar 1')
    popen(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.8)
    return capture_points(wait_menu(run), run)
