"""The vendored branding files: `cosmyx-src/branding/overlay/<path>`.

Every overlay file replaces the upstream file at the same repository-relative
path (or creates it, when upstream has none). The overlay lives outside
`resources/` because CMake installs that folder whole.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import BrandingError, repo_path
from . import OVERLAY_DIR
from .manifest import Manifest, overlay_files, overlay_path


def symlink_in(root: Path, path: str) -> bool:
    """True when the overlay file of `path`, or a folder between it and the
    overlay root, is a symlink. Git checks a symlink out as a plain text file
    holding its target on Windows, so its content would differ by OS."""
    current = repo_path(root, OVERLAY_DIR)
    for part in path.split("/"):
        current = current / part
        if current.is_symlink():
            return True
    return False


def targets(root: Path, manifest: Manifest) -> list[str]:
    """Paths the overlay stage writes: rows with an override and an overlay file."""
    present = set(overlay_files(root))
    return sorted(row["path"] for _, row in manifest.rows() if row["override_sha256"] and row["path"] in present)


def apply(root: Path, manifest: Manifest, before_write=None) -> list[str]:
    """Copy every overlay file onto its upstream path. Returns the paths written."""
    written = []
    for path in targets(root, manifest):
        if before_write is not None:
            before_write(path)
        source = overlay_path(root, path)
        if symlink_in(root, path):
            raise BrandingError(f"{path}: the overlay file is a symlink; commit the file itself")
        destination = repo_path(root, path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        written.append(path)
    return written
