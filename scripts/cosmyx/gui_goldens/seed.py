"""Clean data folder for one pass (decision 0170).

tests/cosmyx/gui/fixtures/OrcaSlicer.conf.in becomes <datadir>/<app key>.conf:
setup wizard marked finished, the current version (no upgrade notice),
no daily tips, no splash screen, en_US, an update URL that points nowhere,
a fixed window geometry and pinned printer, process and filament presets.
Nothing of the runner's own settings can leak into a capture.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from . import GUI_DIR, GoldenError

TEMPLATE = GUI_DIR / "fixtures" / "OrcaSlicer.conf.in"
VERSION = re.compile(r'^\s*set\(\s*SoftFever_VERSION\s+"([^"]+)"\s*\)', re.MULTILINE)
PLACEHOLDER = re.compile(r"@[A-Z_]+@")
APP_KEY = re.compile(r'^\s*set\(\s*SLIC3R_APP_KEY\s+"([^"]+)"\s*\)', re.MULTILINE)


def identity(version_inc: Path) -> tuple[str, str]:
    """(SLIC3R_APP_KEY, SoftFever_VERSION) of the built commit."""
    text = version_inc.read_text(encoding="utf-8")
    key, version = APP_KEY.search(text), VERSION.search(text)
    if not key or not version:
        raise GoldenError(f"{version_inc}: no SLIC3R_APP_KEY or SoftFever_VERSION")
    return key.group(1), version.group(1)


def render(template: str, version: str) -> str:
    text = template.replace("@VERSION@", version)
    if PLACEHOLDER.search(text):
        raise GoldenError("the config template has an unknown @PLACEHOLDER@")
    json.loads(text)
    return text


def seed(datadir: Path, version_inc: Path, template: Path = TEMPLATE) -> Path:
    """Empties `datadir` in place (never deletes the folder itself: SMB rule)
    and writes the seeded config. Returns the config path."""
    datadir.mkdir(parents=True, exist_ok=True)
    for child in datadir.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    key, version = identity(version_inc)
    config = datadir / f"{key}.conf"
    config.write_text(render(template.read_text(encoding="utf-8"), version), encoding="utf-8", newline="\n")
    return config
