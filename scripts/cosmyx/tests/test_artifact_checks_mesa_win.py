"""mesa_win: the pin, the download with its SHA-256 check, the 7-Zip command,
the per-file hashes and the app environment, with a fake opener and runner."""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import inventory, mesa_win  # noqa: E402

ARCHIVE = b"fake 7z archive"
FILES = {"x64/opengl32.dll": b"opengl32", "x64/libgallium_wgl.dll": b"gallium"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def expectations(archive: bytes = ARCHIVE, files: dict[str, bytes] | None = None) -> dict:
    files = FILES if files is None else files
    return {"mesa_win": {"version": "1.0", "url": "https://example.invalid/r/1.0/mesa3d-1.0-release-msvc.7z",
                         "sha256": sha(archive), "files": {k: sha(v) for k, v in files.items()},
                         "env": {"GALLIUM_DRIVER": "llvmpipe"}}}


class Opener:
    def __init__(self, payloads: list) -> None:
        self.payloads, self.calls = list(payloads), 0

    def __call__(self, url, timeout=None):
        self.calls += 1
        payload = self.payloads.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return io.BytesIO(payload)


class SevenZip:
    """Writes the members it is asked for, with the given contents, into -o<dir>."""

    def __init__(self, contents: dict[str, bytes], code: int = 0) -> None:
        self.contents, self.code, self.calls = contents, code, []

    def __call__(self, args, **_kwargs):
        args = [str(a) for a in args]
        self.calls.append(args)
        target = Path(next(a for a in args if a.startswith("-o"))[2:])
        if self.code == 0:
            for member in args[5:]:
                if member in self.contents:
                    (target / member.split("/")[-1]).write_bytes(self.contents[member])
        return subprocess.CompletedProcess(args, self.code, "", "" if self.code == 0 else "ERROR: bad archive")


class PinTests(unittest.TestCase):
    def test_shipped_pin_is_complete(self) -> None:
        data = inventory.load_expectations()
        pin = mesa_win.load_pin(data)
        self.assertRegex(pin.sha256, r"^[0-9a-f]{64}$")
        self.assertTrue(pin.url.startswith("https://github.com/pal1000/mesa-dist-win/releases/download/"))
        self.assertIn(f"/{pin.version}/", pin.url)
        self.assertTrue(pin.asset.endswith("-release-msvc.7z"))
        self.assertIn("x64/opengl32.dll", pin.files)
        for digest in pin.files.values():
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(data["mesa_win"]["license"], "MIT")


class PrepareTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.app, self.work = root / "app", root / "work"
        self.app.mkdir()

    def prepare(self, opener, seven_zip=None, data=None, env=None):
        return mesa_win.prepare(self.app, self.work, data or expectations(), env or {"PATH": "sysbin"},
                                seven_zip or SevenZip(FILES), opener, seven_zip="7z.exe", pause=0)

    def test_ready(self) -> None:
        tool = SevenZip(FILES)
        prepared = mesa_win.prepare(self.app, self.work, expectations(), {"Path": "sysbin"}, tool,
                                    Opener([ARCHIVE]), seven_zip="7z.exe", pause=0)
        self.assertEqual((self.app / "mesa" / "opengl32.dll").read_bytes(), b"opengl32")
        self.assertEqual((self.app / "mesa" / "libgallium_wgl.dll").read_bytes(), b"gallium")
        self.assertEqual(prepared.env["Path"].split(os.pathsep), [str(self.app / "mesa"), "sysbin"])
        self.assertNotIn("PATH", prepared.env)
        self.assertEqual(prepared.env["GALLIUM_DRIVER"], "llvmpipe")
        self.assertEqual(prepared.details["mesa"], "1.0")
        command = tool.calls[0]
        self.assertEqual(command[:3], ["7z.exe", "e", "-y"])
        self.assertTrue(command[3].startswith("-o"))
        self.assertEqual(command[5:], sorted(FILES))

    def test_archive_hash_mismatch_fails_and_is_deleted(self) -> None:
        with self.assertRaises(mesa_win.MesaError) as caught:
            self.prepare(Opener([b"tampered"]))
        self.assertEqual(caught.exception.status, "fail")
        self.assertIn("SHA-256", caught.exception.reason)
        self.assertFalse(mesa_win.archive_path(mesa_win.load_pin(expectations()), self.work, {}).exists())

    def test_file_hash_mismatch_fails(self) -> None:
        bad = dict(FILES, **{"x64/opengl32.dll": b"other"})
        with self.assertRaises(mesa_win.MesaError) as caught:
            self.prepare(Opener([ARCHIVE]), SevenZip(bad))
        self.assertEqual(caught.exception.status, "fail")
        self.assertIn("x64/opengl32.dll", caught.exception.reason)
        self.assertFalse((self.app / "mesa").exists())

    def test_missing_member_fails(self) -> None:
        with self.assertRaises(mesa_win.MesaError) as caught:
            self.prepare(Opener([ARCHIVE]), SevenZip({"x64/opengl32.dll": b"opengl32"}))
        self.assertIn("no x64/libgallium_wgl.dll", caught.exception.reason)

    def test_seven_zip_error_fails(self) -> None:
        with self.assertRaises(mesa_win.MesaError) as caught:
            self.prepare(Opener([ARCHIVE]), SevenZip(FILES, code=2))
        self.assertEqual(caught.exception.status, "fail")
        self.assertIn("exit 2", caught.exception.reason)

    def test_missing_seven_zip_skips(self) -> None:
        opener = Opener([ARCHIVE])
        with self.assertRaises(mesa_win.MesaError) as caught:
            mesa_win.prepare(self.app, self.work, expectations(), {}, SevenZip(FILES), opener, seven_zip="")
        self.assertEqual(caught.exception.status, "skip")
        self.assertIn("7-Zip", caught.exception.reason)
        self.assertEqual(opener.calls, 0)

    def test_network_errors_are_retried_then_fail(self) -> None:
        opener = Opener([urllib.error.URLError("down"), ARCHIVE])
        self.prepare(opener)
        self.assertEqual(opener.calls, 2)
        opener = Opener([urllib.error.URLError("down")] * 3)
        downloads = self.work / "mesa-download"
        for leftover in downloads.glob("*"):
            leftover.unlink()
        with self.assertRaises(mesa_win.MesaError) as caught:
            self.prepare(opener)
        self.assertEqual(caught.exception.status, "fail")
        self.assertEqual(opener.calls, 3)
        self.assertEqual(list(downloads.glob("*.part")), [])

    def test_cache_is_reused_only_when_its_hash_matches(self) -> None:
        cache = Path(self.tmp.name) / "cache"
        env = {mesa_win.CACHE_ENV: str(cache)}
        cache.mkdir()
        pin = mesa_win.load_pin(expectations())
        (cache / pin.asset).write_bytes(ARCHIVE)
        opener = Opener([])
        mesa_win.prepare(self.app, self.work, expectations(), env, SevenZip(FILES), opener, seven_zip="7z", pause=0)
        self.assertEqual(opener.calls, 0)
        (cache / pin.asset).write_bytes(b"stale")
        opener = Opener([ARCHIVE])
        mesa_win.prepare(self.app, self.work, expectations(), env, SevenZip(FILES), opener, seven_zip="7z", pause=0)
        self.assertEqual(opener.calls, 1)
        self.assertEqual((cache / pin.asset).read_bytes(), ARCHIVE)

    def test_fetch_fills_the_given_mesa_folder(self) -> None:
        from unittest import mock
        with mock.patch.object(mesa_win, "load_pin", return_value=mesa_win.load_pin(expectations())):
            found = mesa_win.fetch(self.app / "mesa", self.work, {}, run=SevenZip(FILES), opener=Opener([ARCHIVE]),
                                   seven_zip="7z", pause=0)
        self.assertEqual(found, self.app / "mesa")
        self.assertTrue((self.app / "mesa" / "opengl32.dll").is_file())
        with self.assertRaises(ValueError):
            mesa_win.fetch(self.app / "other")


if __name__ == "__main__":
    unittest.main()
