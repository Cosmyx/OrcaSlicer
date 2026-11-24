"""Run the Cosmyx tooling script tests.

- test_*.py files in scripts/cosmyx/tests run with the standard library
  unittest runner.
- *.Tests.ps1 files run with Pester. When no PowerShell is installed, Pester is
  skipped with a message, unless COSMYX_REQUIRE_PESTER=1 is set (the Windows CI
  leg sets it), in which case a missing PowerShell is an error.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent / "tests"


def find_powershell() -> str | None:
    """Return the PowerShell executable to run Pester with, if any."""
    for name in ("pwsh", "powershell"):
        path = shutil.which(name)
        if path:
            return path
    return None


def pester_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.Tests.ps1"))


def run_python_tests(directory: Path) -> bool:
    suite = unittest.defaultTestLoader.discover(str(directory), pattern="test_*.py", top_level_dir=str(directory))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return result.wasSuccessful()


def run_pester_tests(directory: Path, powershell: str | None, require: bool) -> bool:
    files = pester_files(directory)
    if not files:
        print("Pester: no *.Tests.ps1 files, nothing to run.")
        return True
    if powershell is None:
        if require:
            print("Pester: PowerShell is required (COSMYX_REQUIRE_PESTER=1) but not installed.", file=sys.stderr)
            return False
        print("Pester skipped: PowerShell (pwsh) is not installed on this machine.")
        return True
    # PowerShell single-quoted strings escape a quote by doubling it.
    quoted_dir = str(directory).replace("'", "''")
    command = (
        "$ErrorActionPreference = 'Stop'; Import-Module Pester -MinimumVersion 5.0; "
        "$config = New-PesterConfiguration; "
        f"$config.Run.Path = '{quoted_dir}'; "
        "$config.Run.Exit = $true; $config.Output.Verbosity = 'Detailed'; "
        "Invoke-Pester -Configuration $config"
    )
    completed = subprocess.run([powershell, "-NoLogo", "-NoProfile", "-Command", command], check=False)
    return completed.returncode == 0


def main() -> int:
    require = os.environ.get("COSMYX_REQUIRE_PESTER") == "1"
    python_ok = run_python_tests(TESTS_DIR)
    pester_ok = run_pester_tests(TESTS_DIR, find_powershell(), require)
    return 0 if python_ok and pester_ok else 1


if __name__ == "__main__":
    sys.exit(main())
