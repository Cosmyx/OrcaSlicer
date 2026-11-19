"""linux: manifest and checksums, smoke rules, ELF machines and the job flow
with a fake runner; the running interpreter as a real ELF file on Linux."""

from __future__ import annotations

import json
import signal
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import inventory, linux  # noqa: E402
from artifact_checks.records import build_manifest, sha256sums  # noqa: E402

TAG = "2.6.0-dev-8_aa9dac8"
EXPECTATIONS = inventory.load_expectations()


def elf(machine: int) -> bytes:
    data = bytearray(64)
    data[:4] = b"\x7fELF"
    data[4], data[5] = 2, 1
    struct.pack_into("<H", data, 18, machine)
    struct.pack_into("<Q", data, 0x28, 64)
    struct.pack_into("<HH", data, 0x3A, 64, 0)
    return bytes(data)


class ManifestTests(unittest.TestCase):
    def test_manifest_is_sorted_posix_with_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "b dir").mkdir()
            (root / "b dir" / "z.txt").write_bytes(b"z")
            (root / "a.txt").write_bytes(b"")
            manifest = build_manifest(root)
            self.assertEqual([e["path"] for e in manifest], ["a.txt", "b dir/z.txt"])
            self.assertEqual(manifest[0]["sha256"], "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
            self.assertEqual(manifest[1]["size"], 1)
            sums = sha256sums([("x/b dir/z.txt", root / "b dir" / "z.txt"), ("x/a.txt", root / "a.txt")])
            self.assertEqual(sums.splitlines()[0].split("  ")[1], "x/a.txt")
            self.assertTrue(sums.endswith("\n"))


class SmokeTests(unittest.TestCase):
    def test_rules(self) -> None:
        cases = [
            ((0, "", False), "pass"),
            ((1, "Usage: orca-slicer [ OPTIONS ]", False), "pass"),
            ((1, "cannot open display", False), "fail"),
            ((-signal.SIGSEGV, "", False), "fail"),
            ((128 + signal.SIGABRT, "", False), "fail"),
            ((None, "", True), "fail"),
        ]
        for (code, output, timed_out), expected in cases:
            with self.subTest(code=code, output=output):
                self.assertEqual(linux.smoke_status(code, output, timed_out, 60)[0], expected)

    def test_timeout_and_command(self) -> None:
        calls = []

        def hang(args, **kwargs):
            calls.append((args, kwargs))
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])

        record = linux.smoke("app", Path("root/AppRun"), 60, hang)
        self.assertEqual(record.status, "fail")
        self.assertEqual(calls[0][0][:2], ["xvfb-run", "-a"])
        self.assertEqual(calls[0][0][-1], "--help")
        self.assertEqual(calls[0][1]["timeout"], 60)


class ElfTests(unittest.TestCase):
    def test_elf_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "usr" / "lib").mkdir(parents=True)
            (root / "AppRun").write_bytes(elf(0x3E))
            (root / "usr" / "lib" / "libx.so").write_bytes(elf(0xB7))
            statuses = {r.path: r.status for r in linux.elf_records("app", root, "x86_64")}
            self.assertEqual(statuses, {"AppRun": "pass", "usr/lib/libx.so": "fail"})
            self.assertEqual(linux.elf_records("app", root / "usr" / "lib" / "none", "x86_64")[0].status, "fail")

    @unittest.skipUnless(sys.platform.startswith("linux"), "the running interpreter is an ELF file on Linux only")
    def test_real_interpreter(self) -> None:
        import platform
        expected = {"x86_64": "x86_64", "aarch64": "aarch64"}.get(platform.machine())
        if expected is None:
            self.skipTest(f"machine {platform.machine()} not covered")
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "python"
            target.write_bytes(Path(sys.executable).resolve().read_bytes())
            self.assertEqual(linux.elf_records("py", Path(tmp), expected)[0].status, "pass")


class CheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.artifacts, self.work, self.subject = root / "artifacts", root / "work", root / "subject"
        self.subject.mkdir()
        (self.subject / "version.inc").write_text('set(SLIC3R_APP_NAME "OrcaSlicer")\nset(SoftFever_VERSION "2.6.0-dev")\n',
                                                  encoding="utf-8")
        for name, data in ((f"OrcaSlicer_Linux_ubuntu_2404_{TAG}", elf(0x3E)),
                           (f"OrcaSlicer_Linux_ubuntu_2404_aarch64_{TAG}", elf(0xB7)),
                           (f"OrcaSlicer_profile_validator_Linux_ubuntu_2404_{TAG}", elf(0x3E))):
            (self.artifacts / name).mkdir(parents=True)
            (self.artifacts / name / "file.AppImage").write_bytes(data)
        self.calls = []

    def fake_run(self, args, **kwargs):
        args = [str(a) for a in args]
        self.calls.append(args)
        if args[-1] == "--appimage-extract":
            root = Path(kwargs["cwd"]) / "squashfs-root"
            (root / "resources" / "i18n").mkdir(parents=True)
            (root / "resources" / "profiles").mkdir()
            (root / "resources" / "cosmyx" / "models").mkdir(parents=True)
            (root / "resources" / "cosmyx" / "models" / "cosmyx_cube.3mf").write_bytes(b"3mf")
            (root / "AppRun").write_bytes(elf(0x3E))
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[-1] == "--help":
            return subprocess.CompletedProcess(args, 0, "Usage:", "")
        if "--slice" in args:
            out = Path(args[args.index("--outputdir") + 1])
            (out / "result.json").write_text(json.dumps({"return_code": 0}), encoding="utf-8")
            gcode = "; HEADER_BLOCK_START\n; generated by OrcaSlicer 2.6.0-dev on 2026-11-19\n; CONFIG_BLOCK_START\n"
            gcode += ";TYPE:Outer wall\n" + "G1 X1 Y1 E0.1\n" * 120
            (out / "plate_1.gcode").write_text(gcode, encoding="utf-8")
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(f"unexpected {args}")

    def artifacts_list(self):
        return [inventory.classify(p.name, EXPECTATIONS) for p in sorted(self.artifacts.iterdir())]

    def test_full_flow(self) -> None:
        manifests = {}
        hooked = []
        records = linux.check(self.artifacts, self.artifacts_list(), self.work, self.subject, EXPECTATIONS, True,
                              self.fake_run, lambda a, tree: hooked.append(a.name) or [], manifests)
        x64 = {r.check: r.status for r in records if r.artifact == f"OrcaSlicer_Linux_ubuntu_2404_{TAG}"}
        self.assertEqual((x64["elf"], x64["smoke"], x64["slice"]), ("pass", "pass", "pass"))
        aarch = [r for r in records if "aarch64" in r.artifact]
        self.assertEqual({r.check: r.status for r in aarch}, {"elf": "pass", "smoke": "skip", "slice": "skip"})
        self.assertTrue(all(r.by_design for r in aarch if r.status == "skip"))
        self.assertEqual(len(hooked), 1)
        self.assertIn("AppRun", [e["path"] for e in next(iter(manifests.values()))])
        validator = next(r for r in records if "validator" in r.artifact)
        self.assertEqual(validator.status, "pass")

    def test_fork_build_is_never_executed(self) -> None:
        records = linux.check(self.artifacts, self.artifacts_list(), self.work, self.subject, EXPECTATIONS, False,
                              self.fake_run)
        self.assertFalse(any(c[-1] in ("--appimage-extract", "--help") or "--slice" in c for c in self.calls))
        x64 = [r for r in records if r.artifact == f"OrcaSlicer_Linux_ubuntu_2404_{TAG}"]
        # Without unsquashfs on the host the unpack fails cleanly; with it, smoke and slice are skipped.
        self.assertTrue(all(r.status in ("fail", "skip", "pass") for r in x64))
        self.assertFalse(any(r.check in ("smoke", "slice") and r.status == "pass" for r in x64))


if __name__ == "__main__":
    unittest.main()
