"""Breaker test for artifact_checks/policy_windows.py: a damaged MSIX package."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import policy_windows  # noqa: E402
from artifact_checks.inventory import Artifact  # noqa: E402


class DamagedMsixTests(unittest.TestCase):
    def test_a_damaged_msix_is_a_fail_record_not_a_crash(self) -> None:
        """Expected: an .msix that is not a valid zip (truncated download, broken
        packaging step) gives a "fail" record for that artifact and the other
        artifacts are still collected. Actual: zipfile.BadZipFile escapes
        collect() and the whole Windows job dies without writing any record."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = "OrcaSlicer_Windows_MSIX_2.6.0-dev-8_aa9dac8_x64"
            folder = root / "artifacts" / name
            folder.mkdir(parents=True)
            (folder / "OrcaSlicer.msix").write_bytes(b"PK\x03\x04 truncated")
            artifact = Artifact(name, "windows-msix", "windows", "msix", "x64")
            expectations = {"windows": {"nsis_prefixes": [], "seven_zip_min": "23.01"}}
            collected = policy_windows.collect(root / "artifacts", [artifact], root / "work", expectations, {},
                                               install=False)
            self.assertTrue(any(r.status == "fail" and r.artifact == name for r in collected.records),
                            collected.records)


if __name__ == "__main__":
    unittest.main()
