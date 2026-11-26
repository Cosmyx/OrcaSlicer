"""Find what to sign: the apps of the universal build and, inside each one,
every Mach-O file and nested bundle, in inside-out order (decision 0152).

Mach-O files are found by their magic bytes (artifact_checks/binfmt.py), not by
name or by `file`; symbolic links are never followed or signed (the relocated
Python runtime leaves Contents/MacOS/python as a link to Contents/Resources/python).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from . import SigningError, import_artifact_checks

import_artifact_checks()

from artifact_checks import binfmt  # noqa: E402

APPS_DIR = Path("build") / "universal" / "OrcaSlicer"
BUNDLE_SUFFIXES = (".app", ".framework", ".bundle", ".plugin", ".xpc", ".appex")


@dataclass(frozen=True)
class Item:
    path: Path
    kind: str  # macho or bundle

    @property
    def depth(self) -> int:
        return len(self.path.parts)


def find_apps(root: Path) -> list[Path]:
    """Every .app of build/universal/OrcaSlicer under root; none is an error."""
    folder = root / APPS_DIR
    apps = sorted(p for p in folder.iterdir() if p.suffix == ".app" and p.is_dir() and not p.is_symlink()) \
        if folder.is_dir() else []
    if not apps:
        raise SigningError(f"no .app in {APPS_DIR.as_posix()}: the universal build did not run")
    return apps


def is_bundle(path: Path) -> bool:
    if path.suffix not in BUNDLE_SUFFIXES or path.is_symlink() or not path.is_dir():
        return False
    return any((path / marker).exists() for marker in ("Contents/Info.plist", "Resources/Info.plist", "Versions"))


def nested_bundles(app: Path) -> list[Path]:
    found = []
    for folder, dirs, _files in os.walk(app, followlinks=False):
        for name in dirs:
            path = Path(folder) / name
            if is_bundle(path):
                found.append(path)
    return found


def plan(app: Path) -> tuple[list[Item], list[Path]]:
    """(items to sign in order, Mach-O object files left out).

    Deeper paths come first, so everything inside a bundle is signed before the
    bundle seals it; the app itself comes last. Object files (.o) are not
    loadable code and codesign cannot sign them."""
    machos, objects = [], []
    for path, fmt in binfmt.walk(app, "macho"):
        (objects if fmt.is_object else machos).append(path)
    if not machos:
        raise SigningError(f"no Mach-O file found in {app.name}: detection is broken")
    items = [Item(p, "macho") for p in machos] + [Item(p, "bundle") for p in nested_bundles(app)]
    # Stable order: deepest first, files before bundles at the same depth, then by path.
    items.sort(key=lambda item: (-item.depth, item.kind != "macho", item.path.as_posix()))
    items.append(Item(app, "bundle"))
    return items, sorted(objects)
