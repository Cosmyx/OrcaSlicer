"""Breaker tests for the smoke runs (artifact_checks/linux.py and
smoke_native.py): an app that prints bytes that are not valid text."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import linux, smoke_native  # noqa: E402

# Bytes that are invalid in UTF-8 and undefined in cp1252, so the locale
# decoding fails on every OS.
SCRIPT = "import sys\nsys.stdout.buffer.write(b'usage: \\x81\\x8d\\xff\\n')\nsys.exit(1)\n"


def python_runner(script: Path):
    """Run `<app> --help` as `python <script> --help` (no executable bit needed)."""
    def run(args, **kwargs):
        return subprocess.run([sys.executable, str(script)] + list(args[1:]), **kwargs)
    return run


class SmokeOutputEncodingTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.script = Path(tmp.name) / "app.py"
        self.script.write_text(SCRIPT, encoding="utf-8", newline="\n")

    def test_linux_smoke_survives_undecodable_output(self) -> None:
        """Expected: a smoke record (pass: usage printed, or fail) whatever bytes
        the app prints. Actual: subprocess.run(text=True) decodes strictly and
        UnicodeDecodeError escapes smoke(), killing the Linux job."""
        record = linux.smoke("app", self.script, 30, python_runner(self.script), xvfb=False)
        self.assertEqual(record.check, "smoke")

    def test_native_smoke_survives_undecodable_output(self) -> None:
        """Expected: as above for the Windows and macOS smoke run. Actual:
        UnicodeDecodeError escapes smoke_native.smoke()."""
        record = smoke_native.smoke("windows", "app", self.script, "app --help", 30, python_runner(self.script))
        self.assertEqual(record.check, "smoke")


if __name__ == "__main__":
    unittest.main()
