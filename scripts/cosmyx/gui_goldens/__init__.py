"""Cosmyx GUI goldens: the harness around the in-app driver.

The application, started with COSMYX_GUI_DRIVER_DIR, walks itself through
tests/cosmyx/gui/script.json and writes protocol v1 events (protocol.py). This
package seeds a clean data folder (seed.py), starts the built application
(launch.py), captures the screen on each capture event (capture_*.py, one per
OS: decision 0165), stores canonical PNG files (png.py), and compares them with
the committed goldens (compare.py, tolerance.json: decision 0168).

Entry point: cli.py. Documentation: wiki/cosmyx/gui-goldens.md.
"""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[2]
GUI_DIR = REPO_ROOT / "tests" / "cosmyx" / "gui"
OSES = ("linux", "macos", "windows")


class GoldenError(Exception):
    """A problem that stops a pass: bad input, missing tool, broken protocol."""
