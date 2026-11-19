"""Shared fixture of the branding engine tests: a small fake OrcaSlicer tree.

Not a test module itself (the runner only collects test_*.py).
"""

from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

COSMYX_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = COSMYX_DIR.parents[1]
if str(COSMYX_DIR) not in sys.path:
    sys.path.insert(0, str(COSMYX_DIR))

import branding  # noqa: E402
from branding import apply as apply_module  # noqa: E402
from branding import guards, manifest, overlay, render, textpatch  # noqa: E402
from branding import cli  # noqa: E402

DEV = {}
RELEASE = {"COSMYX_BRAND_REF": "refs/heads/release/2.6"}


def png(width: int, height: int) -> bytes:
    """A tiny valid PNG of the given size (one grey row repeated)."""
    raw = b"".join(b"\x00" + b"\x80" * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def svg(colour: str, size: int = 16, css: bool = False) -> str:
    paint = f'style="fill:{colour}"' if css else f'fill="{colour}"'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}">\n'
        f'  <rect width="{size}" height="{size}" {paint}/>\n</svg>\n'
    )


TREE = {
    "resources/images/OrcaSlicer.svg": svg("#009688", 64),
    "resources/images/apple.svg": svg("#009688"),
    "resources/images/zebra.svg": svg("#26a69a", css=True),
    "resources/images/grey.svg": svg("#808080"),
    "resources/images/green.svg": svg("#00AE42"),
    "resources/web/img/check_g.svg": svg("#00675B", 20),
    "resources/web/css/global.css": ":root { --main-color: #009688; }\n",
    "src/slic3r/GUI/Widget.cpp": 'auto c = wxColour(0, 150, 136); // brand\nauto h = "#009688";\n',
    "version.inc": 'set(SLIC3R_APP_NAME "OrcaSlicer")\nset(SLIC3R_APP_KEY "OrcaSlicer")\n',
    "README.md": "OrcaSlicer\n",
    ".gitignore": "/build*/\n",
}
BINARY = {
    "resources/images/OrcaSlicer_32px.png": png(32, 32),
    "scripts/msix/assets/StoreLogo.png": png(50, 50),
}


def git(root: Path, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args], input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )


def write(root: Path, relative: str, content) -> Path:
    path = root.joinpath(*relative.split("/"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
    return path


def read(root: Path, relative: str) -> bytes:
    return root.joinpath(*relative.split("/")).read_bytes()


def snapshot(root: Path) -> dict:
    """{relative path: bytes} of every file outside .git and build/."""
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_file() and not relative.startswith((".git/", "build/")):
            result[relative] = path.read_bytes()
    return result


class TreeCase(unittest.TestCase):
    """A fresh fake tree per test, synced into a manifest; optionally a git repo."""

    use_git = False

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for relative, content in {**TREE, **BINARY}.items():
            write(self.root, relative, content)
        write(self.root, f"{branding.OVERLAY_DIR}/.gitkeep", b"")
        self.sync()
        if self.use_git:
            git(self.root, "init", "-q")
            git(self.root, "config", "user.name", "Test")
            git(self.root, "config", "user.email", "test@example.invalid")
            git(self.root, "config", "core.autocrlf", "false")
            self.commit("init")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def commit(self, message: str) -> None:
        git(self.root, "add", "-A")
        self.assertEqual(git(self.root, "commit", "-q", "-m", message).returncode, 0)

    def sync(self) -> dict:
        stats = manifest.sync(self.root)
        render.write(self.root, manifest.load(self.root))
        return stats

    def add_overlay(self, relative: str, content, sync: bool = True) -> None:
        write(self.root, f"{branding.OVERLAY_DIR}/{relative}", content)
        if sync:
            self.sync()

    def ctx(self, env: dict | None = None, plugins: dict | None = None):
        return apply_module.Context(self.root, DEV if env is None else env, plugins or {})

    def findings(self, phase: str = "pre", env: dict | None = None, guard: str | None = None, ctx=None):
        found = guards.run(ctx or self.ctx(env), phase)
        return [finding for finding in found if guard is None or finding.guard == guard]

    def apply(self, env: dict | None = None, plugins: dict | None = None, ci: bool = False) -> tuple:
        lines = []
        code = apply_module.apply(self.root, ci=ci, env=DEV if env is None else env, out=lines.append, plugins=plugins or {})
        return code, lines

    def write_json(self, relative: str, data) -> None:
        write(self.root, relative, branding.dump_json(data))


__all__ = [
    "BINARY",
    "DEV",
    "RELEASE",
    "REPO_ROOT",
    "TREE",
    "TreeCase",
    "apply_module",
    "branding",
    "cli",
    "git",
    "guards",
    "manifest",
    "overlay",
    "png",
    "read",
    "render",
    "snapshot",
    "svg",
    "textpatch",
    "write",
]
