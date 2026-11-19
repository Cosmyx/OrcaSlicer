"""Rebuild each app's DMG from the signed, stapled app (decision 0154).

"Create DMG without notary" already wrote the DMGs from the unsigned apps; they
are rebuilt under the same names, `<app>_Mac_universal_<version>.dmg` in the
workspace, so the upstream upload steps pick up the signed ones unchanged.
The image itself is made by upstream's scripts/create_dmg.sh (with its retry).
"""

from __future__ import annotations

import os
import plistlib
import shlex
import shutil
from pathlib import Path
from xml.parsers.expat import ExpatError

from . import Context, REPO_ROOT

# What plistlib raises on a damaged file besides InvalidFileException (a
# ValueError): expat errors for broken XML, and lookup or type errors from
# malformed values such as a bad <date>.
PLIST_ERRORS = (OSError, ValueError, ExpatError, AttributeError, KeyError, TypeError, OverflowError, RecursionError)


def dmg_name(app: Path, version: str) -> str:
    return f"{app.stem}_Mac_universal_{version}.dmg"


def volume_name(app: Path) -> str:
    try:
        with open(app / "Contents" / "Info.plist", "rb") as handle:
            info = plistlib.load(handle)
    except PLIST_ERRORS:
        info = None
    # A valid plist may still have any shape: only a string name in a dict counts.
    name = info.get("CFBundleName") if isinstance(info, dict) else None
    return name if isinstance(name, str) and name.strip() else app.stem


def empty_folder(folder: Path) -> None:
    """Empty a folder in place (never delete and recreate it, see the SMB rule)."""
    folder.mkdir(parents=True, exist_ok=True)
    for child in folder.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def build(ctx: Context, app: Path, root: Path, version: str) -> Path:
    staging = app.parent.parent / f"{app.stem}_dmg"
    empty_folder(staging)
    ctx.must(["ditto", str(app), str(staging / app.name)], f"ditto {app.name}")
    os.symlink("/Applications", staging / "Applications")
    output = root / dmg_name(app, version)
    scripts = REPO_ROOT / "scripts"
    command = (f"source {shlex.quote(str(scripts / 'retry.sh'))}; source {shlex.quote(str(scripts / 'create_dmg.sh'))}; "
               f"create_dmg {shlex.quote(volume_name(app))} {shlex.quote(str(staging))} {shlex.quote(str(output))}")
    ctx.must(["bash", "-c", command], f"create_dmg {output.name}")
    ctx.say(f"built {output.name}")
    return output
