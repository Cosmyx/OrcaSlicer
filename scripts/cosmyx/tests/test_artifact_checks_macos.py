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
        if args[:3] == ["codesign", "-d", "--verbose=4"]:
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


TEAM = "TEAM123456"
DEVELOPER_ID = f"""Executable=/x
CodeDirectory v=20500 size=1 flags=0x10000(runtime) hashes=1+7 location=embedded
Authority=Developer ID Application: Example Corp ({TEAM})
Authority=Developer ID Certification Authority
Timestamp=19 Nov 2026 at 10:00:00
TeamIdentifier={TEAM}
"""


class SignedTools(FakeTools):
    """A Developer ID signed, notarised build; `broken` names files whose
    signature, stapling or Gatekeeper answer is wrong."""

    def __init__(self, archs: dict[str, str], display: str = DEVELOPER_ID, broken: set[str] | None = None) -> None:
        super().__init__(archs, set(archs) | {"OrcaSlicer.app", "OrcaSlicer.dmg"}, display)
        self.broken = broken or set()

    def __call__(self, args, **kwargs):
        args = [str(a) for a in args]
        name = Path(args[-1]).name
        if args[:3] == ["codesign", "-d", "--verbose=4"]:
            self.calls.append(args)
            text = self.dv.replace("flags=0x10000(runtime)", "flags=0x0(none)") if name in self.broken else self.dv
            return subprocess.CompletedProcess(args, 0, "", text)
        if args[:3] == ["xcrun", "stapler", "validate"]:
            self.calls.append(args)
            return subprocess.CompletedProcess(args, 65 if name in self.broken else 0, "", "")
        if args[0] == "spctl":
            self.calls.append(args)
            source = "Unnotarized Developer ID" if name in self.broken else "Notarized Developer ID"
            return subprocess.CompletedProcess(args, 0, "", f"{args[-1]}: accepted\nsource={source}\n")
        return super().__call__(args, **kwargs)


class EnforceTests(unittest.TestCase):
    """Decision 0156: Developer ID rules once the build is signed."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mount = Path(self.tmp.name) / "mnt"
        macos_dir = self.mount / "OrcaSlicer.app" / "Contents" / "MacOS"
        macos_dir.mkdir(parents=True)
        (macos_dir / "OrcaSlicer").write_bytes(fat_header())
        self.archs = {"OrcaSlicer": "x86_64 arm64"}

    def scan(self, tools, team=TEAM, name=f"OrcaSlicer_Mac_universal_{TAG}"):
        return macos.scan_tree(artifact(name), self.mount, allowlist.Allowlist(), tools, macos.signing_policy.ENFORCE,
                               team)

    def by_check(self, records):
        found = {}
        for record in records:
            found.setdefault(record.check, []).append(record.status)
        return found

    def test_signed_build_passes(self) -> None:
        checks = self.by_check(self.scan(SignedTools(self.archs)))
        self.assertEqual(checks["macho_identity"], ["pass"])
        self.assertEqual(checks["bundle_sig"], ["pass"])

    def test_wrong_team_and_missing_runtime_fail(self) -> None:
        checks = self.by_check(self.scan(SignedTools(self.archs), team="OTHERTEAM1"))
        self.assertEqual(checks["macho_identity"], ["fail"])
        self.assertEqual(checks["bundle_sig"], ["fail"])
        records = self.scan(SignedTools(self.archs, broken={"OrcaSlicer"}))
        identity = next(r for r in records if r.check == "macho_identity")
        self.assertEqual(identity.status, "fail")
        self.assertIn("no hardened runtime", identity.reason)

    def test_adhoc_build_fails_in_enforce_mode(self) -> None:
        tools = SignedTools(self.archs, display="Signature=adhoc\nTeamIdentifier=not set\n")
        checks = self.by_check(self.scan(tools))
        self.assertEqual(checks["macho_identity"], ["fail"])
        self.assertEqual(checks["bundle_sig"], ["fail"])

    def test_report_mode_runs_no_identity_check(self) -> None:
        records = macos.scan_tree(artifact(), self.mount, allowlist.Allowlist(), SignedTools(self.archs))
        self.assertNotIn("macho_identity", self.by_check(records))

    def test_dmg_signature_and_notarisation(self) -> None:
        dmg = Path(self.tmp.name) / "OrcaSlicer.dmg"
        records = macos.dmg_records(artifact(), dmg, self.mount, TEAM, SignedTools(self.archs))
        self.assertEqual([(r.check, r.path, r.status) for r in records],
                         [("dmg_sig", "OrcaSlicer.dmg", "pass"), ("notarization", "OrcaSlicer.dmg", "pass"),
                          ("notarization", "OrcaSlicer.app", "pass")])
        tools = SignedTools(self.archs, broken={"OrcaSlicer.app", "OrcaSlicer.dmg"})
        records = macos.dmg_records(artifact(), dmg, self.mount, TEAM, tools)
        notarization = [r for r in records if r.check == "notarization"]
        self.assertTrue(all(r.status == "fail" for r in notarization))
        self.assertIn("not stapled", notarization[0].reason)
        self.assertIn("Gatekeeper", notarization[1].reason)
        open_call = next(c for c in tools.calls if c[0] == "spctl" and "open" in c)
        self.assertIn("context:primary-signature", open_call)

    def check(self, mode, team=TEAM, strict=False, name=f"OrcaSlicer_Mac_universal_{TAG}"):
        artifacts = Path(self.tmp.name) / "artifacts"
        folder = artifacts / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "OrcaSlicer.dmg").write_bytes(b"dmg")
        return macos.check(artifacts, [artifact(name)], Path(self.tmp.name) / "work", allowlist.Allowlist(),
                           SignedTools(self.archs), mode=mode, team=team, strict=strict)

    def test_check_enforce_adds_dmg_records_for_signed_families_only(self) -> None:
        enforce = macos.signing_policy.ENFORCE
        checks = self.by_check(self.check(enforce))
        self.assertIn("dmg_sig", checks)
        self.assertIn("notarization", checks)
        per_arch = self.by_check(self.check(enforce, name=f"OrcaSlicer_Mac_arm64_{TAG}"))
        self.assertNotIn("dmg_sig", per_arch)
        self.assertNotIn("macho_identity", per_arch)

    def test_check_enforce_without_team_fails(self) -> None:
        records = self.check(macos.signing_policy.ENFORCE, team="")
        self.assertTrue(any(r.status == "fail" and "COSMYX_MAC_TEAM_ID" in r.reason for r in records))

    def test_not_configured_fails_only_in_strict_mode(self) -> None:
        mode = macos.signing_policy.NOT_CONFIGURED
        self.assertFalse(any(r.artifact == "signing" for r in self.check(mode)))
        strict = [r for r in self.check(mode, strict=True) if r.artifact == "signing"]
        self.assertEqual([r.status for r in strict], ["fail"])


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
