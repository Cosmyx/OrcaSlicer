"""macos: arch and arm64 signature rules with a patched runner, and with the
real lipo and codesign on a binary compiled at runtime (macOS with cc only)."""

from __future__ import annotations

import datetime as dt
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import allowlist, inventory, macos  # noqa: E402
from undecodable_output import UNDECODABLE, run_printing  # noqa: E402

TAG = "2.6.0-dev-8_aa9dac8"
EXPECTATIONS = inventory.load_expectations()


def artifact(name: str = f"OrcaSlicer_Mac_universal_{TAG}") -> inventory.Artifact:
    return inventory.classify(name, EXPECTATIONS)


def fat_header() -> bytes:
    header = struct.pack(">II", 0xCAFEBABE, 2)
    header += struct.pack(">iiIII", 0x0100000C, 0, 4096, 32, 12)
    header += struct.pack(">iiIII", 0x01000007, 0, 8192, 32, 12)
    data = bytearray(header) + bytes(8192 + 32 - len(header))
    struct.pack_into("<IiII", data, 4096, 0xFEEDFACF, 0x0100000C, 0, 2)
    struct.pack_into("<IiII", data, 8192, 0xFEEDFACF, 0x01000007, 0, 2)
    return bytes(data)


def thin_x86() -> bytes:
    return struct.pack("<IiII", 0xFEEDFACF, 0x01000007, 0, 6) + bytes(32)


class FakeTools:
    """lipo and codesign answers keyed by file name."""

    def __init__(self, archs: dict[str, str], signed: set[str], dv: str = "Signature=adhoc\n") -> None:
        self.archs, self.signed, self.dv, self.calls = archs, signed, dv, []

    def __call__(self, args, **_kwargs):
        args = [str(a) for a in args]
        self.calls.append(args)
        name = Path(args[-1]).name
        if args[:2] == ["lipo", "-archs"]:
            return subprocess.CompletedProcess(args, 0, self.archs[name] + "\n", "")
        if args[:2] == ["codesign", "--verify"]:
            ok = name in self.signed
            return subprocess.CompletedProcess(args, 0 if ok else 1, "", "" if ok else
                                               f"{args[-1]}: code object is not signed at all")
        if args[:2] == ["codesign", "-dv"]:
            return subprocess.CompletedProcess(args, 0, "", self.dv)
        if args[0] == "hdiutil":
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(f"unexpected {args}")


class OutputDecodingTests(unittest.TestCase):
    def test_undecodable_tool_output_is_replaced_not_raised(self) -> None:
        done = macos._run(lambda args, **kwargs: run_printing(args, kwargs, b"bad " + UNDECODABLE + b"\n", 1),
                          ["codesign", "--verify", "x"])
        self.assertIn("\ufffd", macos._last_line(done))


class ScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mount = Path(self.tmp.name) / "mnt"
        macos_dir = self.mount / "OrcaSlicer.app" / "Contents" / "MacOS"
        macos_dir.mkdir(parents=True)
        (macos_dir / "OrcaSlicer").write_bytes(fat_header())
        (macos_dir / "helper").write_bytes(thin_x86())
        (self.mount / "OrcaSlicer.app" / "Contents" / "Info.plist").write_text("<plist/>", encoding="utf-8")

    def statuses(self, records, check):
        return {r.path: r.status for r in records if r.check == check}

    def test_universal_rules(self) -> None:
        tools = FakeTools({"OrcaSlicer": "x86_64 arm64", "helper": "x86_64"}, {"OrcaSlicer", "OrcaSlicer.app"})
        records = macos.scan_tree(artifact(), self.mount, allowlist.Allowlist(), tools)
        arch = self.statuses(records, "arch")
        self.assertEqual(arch["OrcaSlicer.app/Contents/MacOS/OrcaSlicer"], "pass")
        self.assertEqual(arch["OrcaSlicer.app/Contents/MacOS/helper"], "fail")
        sig = self.statuses(records, "macho_sig")
        self.assertEqual(sig["OrcaSlicer.app/Contents/MacOS/OrcaSlicer"], "pass")
        self.assertEqual(sig["OrcaSlicer.app/Contents/MacOS/helper"], "skip")
        bundle = next(r for r in records if r.check == "bundle_sig")
        self.assertEqual(bundle.status, "warn")
        self.assertIn("0146", bundle.reason)
        verify = next(c for c in tools.calls if c[:2] == ["codesign", "--verify"] and "--strict" in c and "--arch" in c)
        self.assertEqual(verify[2:5], ["--strict", "--arch", "arm64"])

    def test_unsigned_arm64_fails(self) -> None:
        tools = FakeTools({"OrcaSlicer": "x86_64 arm64", "helper": "x86_64"}, set())
        records = macos.scan_tree(artifact(), self.mount, allowlist.Allowlist(), tools)
        self.assertEqual(self.statuses(records, "macho_sig")["OrcaSlicer.app/Contents/MacOS/OrcaSlicer"], "fail")

    def test_arch_exempt_entry(self) -> None:
        data = {"version": 1, "entries": [{"os": "macos", "kind": "arch-exempt", "glob": "*/helper",
                                           "reason": "Intel-only tool"}]}
        allow = allowlist.parse(data, dt.date(2026, 1, 1))
        tools = FakeTools({"OrcaSlicer": "x86_64 arm64", "helper": "x86_64"}, {"OrcaSlicer"})
        records = macos.scan_tree(artifact(), self.mount, allow, tools)
        self.assertEqual(self.statuses(records, "arch")["OrcaSlicer.app/Contents/MacOS/helper"], "pass")
        self.assertEqual(allow.stale_records("macos", enforce=True), [])

    def test_per_arch_family(self) -> None:
        tools = FakeTools({"OrcaSlicer": "x86_64 arm64", "helper": "x86_64"}, {"OrcaSlicer"})
        records = macos.scan_tree(artifact(f"OrcaSlicer_Mac_x86_64_{TAG}"), self.mount, allowlist.Allowlist(), tools)
        arch = self.statuses(records, "arch")
        self.assertEqual(arch["OrcaSlicer.app/Contents/MacOS/OrcaSlicer"], "fail")
        self.assertEqual(arch["OrcaSlicer.app/Contents/MacOS/helper"], "pass")

    def test_signature_class(self) -> None:
        self.assertEqual(macos.signature_class("Authority=Developer ID Application: X (TEAM)\n"), "developer-id")
        self.assertEqual(macos.signature_class("Signature=adhoc\n"), "adhoc")
        self.assertEqual(macos.signature_class("x: code object is not signed at all"), "unsigned")

    def test_check_mounts_detaches_and_runs_the_hook(self) -> None:
        artifacts = Path(self.tmp.name) / "artifacts"
        folder = artifacts / f"OrcaSlicer_Mac_universal_{TAG}"
        folder.mkdir(parents=True)
        (folder / "OrcaSlicer.dmg").write_bytes(b"dmg")
        tools = FakeTools({}, set())
        hooked = []
        records = macos.check(artifacts, [artifact()], Path(self.tmp.name) / "work", allowlist.Allowlist(), tools,
                              lambda a, tree: hooked.append(a.name) or [], {})
        self.assertEqual(hooked, [folder.name])
        self.assertTrue(any(c[:2] == ["hdiutil", "attach"] and "-readonly" in c for c in tools.calls))
        self.assertTrue(any(c[:2] == ["hdiutil", "detach"] for c in tools.calls))
        # The empty mount has no Mach-O file.
        self.assertTrue(any(r.status == "fail" and "no Mach-O" in r.reason for r in records))


REAL_TOOLS = sys.platform == "darwin" and all(shutil.which(t) for t in ("cc", "codesign", "lipo"))


@unittest.skipUnless(REAL_TOOLS, "needs macOS with cc, codesign and lipo")
class RealToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mount = Path(self.tmp.name) / "mnt"
        self.mount.mkdir()
        source = Path(self.tmp.name) / "main.c"
        source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
        self.binary = self.mount / "tool"
        done = subprocess.run(["cc", "-arch", "arm64", "-arch", "x86_64", "-o", str(self.binary), str(source)],
                              capture_output=True, text=True, check=False)
        if done.returncode != 0:
            self.skipTest(f"cc cannot build a universal binary here: {done.stderr.strip()[:200]}")

    def records(self):
        return macos.scan_tree(artifact(), self.mount, allowlist.Allowlist(), subprocess.run)

    def test_universal_adhoc_binary_passes(self) -> None:
        subprocess.run(["codesign", "-s", "-", "-f", str(self.binary)], check=True, capture_output=True)
        records = {r.check: r.status for r in self.records()}
        self.assertEqual(records["arch"], "pass")
        self.assertEqual(records["macho_sig"], "pass")

    def test_unsigned_arm64_slice_fails(self) -> None:
        subprocess.run(["codesign", "--remove-signature", str(self.binary)], check=True, capture_output=True)
        records = {r.check: r.status for r in self.records()}
        self.assertEqual(records["arch"], "pass")
        self.assertEqual(records["macho_sig"], "fail")


if __name__ == "__main__":
    unittest.main()
