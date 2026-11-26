"""Cosmyx artifact checks: inspect what a "Build all" run produced.

The package reads the artifacts of a finished build (Windows, macOS and Linux),
collects facts about every binary they ship and turns those facts into check
records (records.py). Policy lives in Python; only the Windows signature facts
come from a PowerShell collector (facts_windows.ps1, decision 0142).

Entry point: cli.py. Documentation: wiki/cosmyx/artifact-checks.md.
"""

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DATA_DIR = PACKAGE_DIR / "data"
