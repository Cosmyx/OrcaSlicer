"""policy_windows: the signature rules from fact records, the payload check,
the 7-Zip gate and the unpacking, with a fake runner (no Windows tool runs)."""

from __future__ import annotations

import datetime as dt
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import allowlist, inventory, policy_windows as pw  # noqa: E402
from artifact_checks.signing_policy import ENFORCE, NOT_CONFIGURED, REPORT  # noqa: E402

OUR_SUBJECT = "CN=Cosmyx, O=Cosmyx, C=FR"
OUR_EKU = "1.3.6.1.4.1.311.97.123456.1"
OUR_EKUS = [pw.CODE_SIGNING_EKU, pw.ARTIFACT_SIGNING_EKU, OUR_EKU]
MS = "CN=Microsoft Corporation, O=Microsoft Corporation, L=Redmond, S=Washington, C=US"
OWN = inventory.load_expectations()["windows"]["own_names"]
TAG = "2.6.0-dev-8_aa9dac8"


def fact(path: str, signer: str | None = OUR_SUBJECT, ekus=None, exit_code: int = 0, status: str = "Valid",
         stamp: str | None = "CN=Microsoft Public RSA Time Stamping Authority", sha: str = "00") -> dict:
    return {"path": path, "sha256": sha, "signtool_exit": exit_code, "signtool_tail": "SignTool Error: x",
            "auth_status": status if signer else "NotSigned", "signer_subject": signer,
            "signer_ekus": OUR_EKUS if ekus is None else ekus, "signer_thumbprint": "AB" if signer else None,
            "timestamp_subject": stamp if signer else None}


def item(name: str, role: str = "portable", artifact: str = "portable-x64") -> pw.Item:
    return pw.Item(artifact, name, name, role, "x64", False, Path("/w") / artifact / name)


def evaluate(facts: list[tuple[pw.Item, dict]], mode: str = ENFORCE, identity: pw.Identity | None = None,
             allow: allowlist.Allowlist | None = None, strict: bool = False):
    items = [i for i, _ in facts]
    by_path = {str(i.file): f for i, f in facts}
    return pw.evaluate(items, by_path, mode, identity or pw.Identity(OUR_SUBJECT, OUR_EKU),
                       allow or allowlist.Allowlist(), OWN, strict)


def signature(records, path: str):
    return next(r for r in records if r.check == "signature" and r.path == path)


class IdentityTests(unittest.TestCase):
    def test_ours_needs_both_artifact_signing_ekus(self) -> None:
        identity = pw.Identity()
        self.assertTrue(pw.is_ours(fact("a"), identity))
        self.assertFalse(pw.is_ours(fact("a", ekus=[pw.CODE_SIGNING_EKU]), identity))
        self.assertFalse(pw.is_ours(fact("a", ekus=[pw.ARTIFACT_SIGNING_EKU]), identity))

    def test_pins_narrow_it(self) -> None:
        self.assertTrue(pw.is_ours(fact("a"), pw.Identity(OUR_SUBJECT, OUR_EKU)))
        self.assertFalse(pw.is_ours(fact("a", signer="CN=Other"), pw.Identity(OUR_SUBJECT, "")))
        other_eku = [pw.CODE_SIGNING_EKU, pw.ARTIFACT_SIGNING_EKU, "1.3.6.1.4.1.311.97.999.1"]
        self.assertFalse(pw.is_ours(fact("a", ekus=other_eku), pw.Identity("", OUR_EKU)))
        self.assertTrue(pw.is_ours(fact("a", signer="CN=Other"), pw.Identity("", OUR_EKU)))

    def test_eku_pin_format(self) -> None:
        records = pw.identity_records(pw.Identity("", "1.2.3"), ENFORCE)
        self.assertEqual(records[0].status, "fail")
        self.assertFalse(pw.is_ours(fact("a", ekus=OUR_EKUS + ["1.2.3"]), pw.Identity("", "1.2.3")))

    def test_no_pin_passes_with_observed_values(self) -> None:
        records = pw.identity_records(pw.Identity(), ENFORCE, [fact("a")])
        self.assertEqual(records[0].status, "warn")
        self.assertEqual(records[0].details, {"subjects": [OUR_SUBJECT], "ekus": [OUR_EKU]})
        self.assertIn(OUR_SUBJECT, records[0].reason)

    def test_subject_pin_only_suggests_eku(self) -> None:
        records = pw.identity_records(pw.Identity(OUR_SUBJECT, ""), ENFORCE, [fact("a")])
        self.assertEqual(records[0].status, "warn")
        self.assertIn("COSMYX_SIGN_EKU", records[0].reason)

    def test_both_pins_and_other_modes_say_nothing(self) -> None:
        self.assertEqual(pw.identity_records(pw.Identity(OUR_SUBJECT, OUR_EKU), ENFORCE), [])
        self.assertEqual(pw.identity_records(pw.Identity(), REPORT), [])


class EnforceTests(unittest.TestCase):
    def test_ours_signed_and_timestamped_passes(self) -> None:
        app = item("orca-slicer.exe")
        self.assertEqual(signature(evaluate([(app, fact(str(app.file)))]), "orca-slicer.exe").status, "pass")

    def test_no_pins_still_passes(self) -> None:
        app = item("orca-slicer.exe")
        records = evaluate([(app, fact(str(app.file)))], identity=pw.Identity())
        self.assertEqual(signature(records, "orca-slicer.exe").status, "pass")
        self.assertNotIn("fail", {r.status for r in records})

    def test_failures(self) -> None:
        cases = {
            "unsigned": dict(signer=None),
            "exit 1": dict(exit_code=1),
            "exit 2": dict(exit_code=2),
            "no timestamp": dict(stamp=None),
            "HashMismatch": dict(status="HashMismatch"),
            "not ours": dict(signer="CN=Someone Else", ekus=[pw.CODE_SIGNING_EKU]),
        }
        for name, options in cases.items():
            with self.subTest(case=name):
                app = item("orca-slicer.exe")
                record = signature(evaluate([(app, fact(str(app.file), **options))]), "orca-slicer.exe")
                self.assertEqual(record.status, "fail")

    def test_vendor_allowlist(self) -> None:
        data = {"version": 1, "entries": [{"os": "windows", "kind": "vendor", "glob": "vcruntime140.dll",
                                           "publisher_subject": MS, "reason": "MSVC runtime"}]}
        dll = item("vcruntime140.dll")
        vendor_fact = fact(str(dll.file), signer=MS, ekus=[pw.CODE_SIGNING_EKU])
        allow = allowlist.parse(data, dt.date(2026, 1, 1))
        self.assertEqual(signature(evaluate([(dll, vendor_fact)], allow=allow), "vcruntime140.dll").status, "pass")
        # Same glob, another publisher.
        allow = allowlist.parse(data, dt.date(2026, 1, 1))
        other = fact(str(dll.file), signer="CN=Other", ekus=[pw.CODE_SIGNING_EKU])
        self.assertEqual(signature(evaluate([(dll, other)], allow=allow), "vcruntime140.dll").status, "fail")
        # Vendor without timestamp.
        allow = allowlist.parse(data, dt.date(2026, 1, 1))
        no_stamp = fact(str(dll.file), signer=MS, ekus=[pw.CODE_SIGNING_EKU], stamp=None)
        self.assertEqual(signature(evaluate([(dll, no_stamp)], allow=allow), "vcruntime140.dll").status, "fail")

    def test_stale_vendor_entry_fails_in_enforce(self) -> None:
        data = {"version": 1, "entries": [{"os": "windows", "kind": "vendor", "glob": "gone.dll",
                                           "publisher_subject": MS, "reason": "old"}]}
        allow = allowlist.parse(data, dt.date(2026, 1, 1))
        app = item("orca-slicer.exe")
        records = evaluate([(app, fact(str(app.file)))], allow=allow)
        self.assertTrue(any(r.path == "gone.dll" and r.status == "fail" for r in records))

    def test_unsigned_ok_never_covers_own_names(self) -> None:
        data = {"version": 1, "entries": [{"os": "windows", "kind": "unsigned-ok", "glob": "*.exe", "reason": "x"}]}
        allow = allowlist.parse(data, dt.date(2026, 1, 1))
        helper, uninstaller = item("helper.exe"), item("Uninstall.exe", role="installed")
        records = evaluate([(helper, fact(str(helper.file), signer=None)),
                            (uninstaller, fact(str(uninstaller.file), signer=None))], allow=allow)
        self.assertEqual(signature(records, "helper.exe").status, "pass")
        self.assertEqual(signature(records, "Uninstall.exe").status, "fail")

    def test_missing_facts_fail(self) -> None:
        records = pw.evaluate([item("a.dll")], {}, ENFORCE, pw.Identity(OUR_SUBJECT, OUR_EKU),
                              allowlist.Allowlist(), OWN, False)
        self.assertEqual(signature(records, "a.dll").status, "fail")

    def test_msix_package_is_unsigned_by_design(self) -> None:
        package = pw.Item("msix", "OrcaSlicer.msix", "OrcaSlicer.msix", "msix-package", "x64")
        record = signature(evaluate([(package, {})]), "OrcaSlicer.msix")
        self.assertEqual(record.status, "pass")
        self.assertIn("by design", record.reason)


class ReportModeTests(unittest.TestCase):
    def test_report_mode_counts_unsigned(self) -> None:
        a, b = item("a.dll"), item("b.dll")
        records = evaluate([(a, fact(str(a.file), signer=None)), (b, fact(str(b.file)))], mode=REPORT)
        self.assertEqual(signature(records, "a.dll").status, "pass")
        summary = next(r for r in records if r.artifact == "summary")
        self.assertEqual((summary.status, summary.details["unsigned"]), ("warn", 1))

    def test_not_configured_notice_and_strict(self) -> None:
        a = item("a.dll")
        summary = next(r for r in evaluate([(a, fact(str(a.file)))], mode=NOT_CONFIGURED) if r.artifact == "summary")
        self.assertEqual(summary.status, "warn")
        self.assertIn("not configured", summary.reason)
        summary = next(r for r in evaluate([(a, fact(str(a.file)))], mode=NOT_CONFIGURED, strict=True)
                       if r.artifact == "summary")
        self.assertEqual(summary.status, "fail")


class PayloadTests(unittest.TestCase):
    def pair(self, payload_sha: str, with_payload: bool = True):
        portable = item("bin/a.dll", "portable", "portable-x64")
        payload = pw.Item("installer-x64", "payload/$INSTDIR/bin/a.dll", "bin/a.dll", "payload", "x64", False,
                          Path("/w/payload/a.dll"))
        facts = [(portable, fact(str(portable.file), sha="AA"))]
        if with_payload:
            facts.append((payload, fact(str(payload.file), sha=payload_sha)))
        return [r for r in evaluate(facts, mode=REPORT) if r.check == "payload"]

    def test_subset_with_same_hashes_passes(self) -> None:
        self.assertEqual([r.status for r in self.pair("aa")], ["pass"])

    def test_hash_mismatch_fails_in_every_mode(self) -> None:
        records = self.pair("bb")
        self.assertEqual(records[0].status, "fail")
        self.assertEqual(records[0].details["different"], ["bin/a.dll"])

    def test_no_installer_is_skipped(self) -> None:
        self.assertEqual([r.status for r in self.pair("aa", with_payload=False)], ["skip"])

    def test_strip_prefix(self) -> None:
        self.assertEqual(pw.strip_prefix("$INSTDIR/resources/x.dll", ["$INSTDIR"]), "resources/x.dll")
        self.assertEqual(pw.strip_prefix("$PLUGINSDIR/nsis.dll", ["$INSTDIR"]), "$PLUGINSDIR/nsis.dll")


class SevenZipTests(unittest.TestCase):
    def test_gate(self) -> None:
        banner = "\n7-Zip 24.09 (x64) : Copyright (c) 1999-2024 Igor Pavlov : 2024-11-29\n"
        self.assertEqual(pw.seven_zip_ok(banner, "23.01"), (True, "7-Zip 24.09"))
        self.assertFalse(pw.seven_zip_ok("7-Zip 22.01 (x64)", "23.01")[0])
        self.assertTrue(pw.seven_zip_ok("7-Zip (a) 23.01 (x64)", "23.01")[0])
        self.assertFalse(pw.seven_zip_ok("", "23.01")[0])


def pe_bytes() -> bytes:
    data = bytearray(0x100)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", data, 0x84, 0x8664)
    return bytes(data)


class CollectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.artifacts, self.work = root / "artifacts", root / "work"
        self.calls: list[list[str]] = []
        portable = self.artifacts / f"OrcaSlicer_Windows_{TAG}_x64_portable"
        (portable / "resources").mkdir(parents=True)
        (portable / "orca-slicer.exe").write_bytes(pe_bytes())
        (portable / "resources" / "readme.txt").write_text("x", encoding="utf-8")
        installer = self.artifacts / f"OrcaSlicer_Windows_{TAG}_x64"
        installer.mkdir()
        (installer / f"OrcaSlicer_Windows_Installer_{TAG}.exe").write_bytes(pe_bytes())
        arm = self.artifacts / f"OrcaSlicer_Windows_{TAG}_arm64"
        arm.mkdir()
        (arm / "OrcaSlicer_Windows_Installer_arm64.exe").write_bytes(pe_bytes())
        msix = self.artifacts / f"OrcaSlicer_Windows_MSIX_{TAG}_x64"
        msix.mkdir()
        with zipfile.ZipFile(msix / f"OrcaSlicer_Windows_MSIX_{TAG}_x64.msix", "w") as archive:
            archive.writestr("VFS/ProgramFilesX64/OrcaSlicer/orca-slicer.exe", pe_bytes())
            archive.writestr("AppxManifest.xml", "<xml/>")
        self.seven_zip = root / "7z.exe"
        self.seven_zip.write_bytes(b"")
        self.banner = "7-Zip 24.09 (x64)"

    def fake_run(self, args, **_kwargs):
        args = [str(a) for a in args]
        self.calls.append(args)
        if args == [str(self.seven_zip)]:
            return subprocess.CompletedProcess(args, 0, self.banner, "")
        if args[1:2] == ["x"]:
            out = Path(args[3][2:]) / "$INSTDIR"
            out.mkdir(parents=True)
            (out / "orca-slicer.exe").write_bytes(pe_bytes())
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[1:2] == ["/S"]:
            target = Path(args[2][3:])
            target.mkdir(parents=True)
            (target / "Uninstall.exe").write_bytes(pe_bytes())
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(f"unexpected command {args}")

    def collect(self, install: bool = True):
        expectations = inventory.load_expectations()
        names = sorted(p.name for p in self.artifacts.iterdir())
        artifacts = [inventory.classify(n, expectations) for n in names]
        return pw.collect(self.artifacts, artifacts, self.work, expectations, {"COSMYX_7Z": str(self.seven_zip)},
                          self.fake_run, install)

    def test_collects_every_pe(self) -> None:
        collected = self.collect()
        roles = sorted((i.role, i.path) for i in collected.items)
        self.assertIn(("portable", "orca-slicer.exe"), roles)
        self.assertIn(("payload", "payload/$INSTDIR/orca-slicer.exe"), roles)
        self.assertIn(("installed", "installed/Uninstall.exe"), roles)
        self.assertIn(("msix", f"OrcaSlicer_Windows_MSIX_{TAG}_x64.msix/VFS/ProgramFilesX64/OrcaSlicer/orca-slicer.exe"),
                      roles)
        self.assertIn(("msix-package", f"OrcaSlicer_Windows_MSIX_{TAG}_x64.msix"), roles)
        payload = next(i for i in collected.items if i.role == "payload")
        self.assertEqual(payload.match_path, "orca-slicer.exe")
        arm_skip = [r for r in collected.records if "arm64" in r.reason]
        self.assertEqual([r.status for r in arm_skip], ["skip"])
        self.assertTrue(arm_skip[0].by_design)
        self.assertEqual([t[0] for t in collected.trees], [f"OrcaSlicer_Windows_{TAG}_x64_portable"])
        install = next(c for c in self.calls if c[1:2] == ["/S"])
        self.assertTrue(install[-1].startswith("/D="), "NSIS needs /D= last")

    def test_old_seven_zip_fails(self) -> None:
        self.banner = "7-Zip 22.01 (x64)"
        collected = self.collect()
        self.assertTrue(any(r.check == "payload" and r.status == "fail" and "23.01" in r.reason
                            for r in collected.records))
        self.assertFalse(any(i.role == "payload" for i in collected.items))

    def test_local_run_never_installs(self) -> None:
        collected = self.collect(install=False)
        self.assertFalse(any(c[1:2] == ["/S"] for c in self.calls))
        self.assertTrue(any("local run" in r.reason for r in collected.records))

    def test_read_facts(self) -> None:
        path = Path(self.tmp.name) / "facts.jsonl"
        path.write_text("\ufeff" + json.dumps(fact("C:/a b/x.dll")) + "\n\n", encoding="utf-8")
        facts = pw.read_facts(path)
        self.assertEqual(list(facts), [str(Path("C:/a b/x.dll"))])


if __name__ == "__main__":
    unittest.main()
