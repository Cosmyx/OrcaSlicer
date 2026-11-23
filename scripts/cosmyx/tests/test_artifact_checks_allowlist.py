"""allowlist: validation, matching, staleness, and the shipped file."""

from __future__ import annotations

import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import allowlist  # noqa: E402

TODAY = dt.date(2026, 11, 19)


def vendor(**extra) -> dict:
    entry = {"os": "windows", "kind": "vendor", "glob": "*/vcruntime140.dll",
             "publisher_subject": "CN=Microsoft Corporation, O=Microsoft Corporation", "reason": "MSVC runtime"}
    entry.update(extra)
    return entry


class ParseTests(unittest.TestCase):
    def test_shipped_allowlist_is_valid_and_empty(self) -> None:
        self.assertEqual(allowlist.load(today=TODAY).entries, [])

    def test_valid_entries(self) -> None:
        data = {"version": 1, "entries": [
            vendor(expires="2027-01-01"),
            {"os": "windows", "kind": "unsigned-ok", "glob": "plugins/*.node", "reason": "no Authenticode"},
            {"os": "macos", "kind": "arch-exempt", "glob": "*/helper", "reason": "Intel only"},
        ]}
        parsed = allowlist.parse(data, TODAY)
        self.assertEqual([e.kind for e in parsed.entries], ["vendor", "unsigned-ok", "arch-exempt"])
        self.assertTrue(parsed.entries[0].require_timestamp)
        self.assertEqual(parsed.entries[0].expires, dt.date(2027, 1, 1))

    def test_invalid_entries(self) -> None:
        cases = {
            "unknown keys": [vendor(thumbprint="AB")],
            "reason is required": [vendor(reason=" ")],
            "expired on": [vendor(expires="2026-11-18")],
            "YYYY-MM-DD": [vendor(expires="soon")],
            "needs publisher_subject": [vendor(publisher_subject="")],
            "os must be": [vendor(os="linux")],
            "kind must be": [vendor(kind="trusted")],
            "glob is required": [vendor(glob="")],
            "are for vendor entries": [{"os": "windows", "kind": "unsigned-ok", "glob": "a", "reason": "r",
                                        "require_timestamp": False}],
        }
        for message, entries in cases.items():
            with self.subTest(message=message):
                with self.assertRaisesRegex(allowlist.AllowlistError, message):
                    allowlist.parse({"version": 1, "entries": entries}, TODAY)
        with self.assertRaises(allowlist.AllowlistError):
            allowlist.parse({"version": 2, "entries": []}, TODAY)
        with self.assertRaises(allowlist.AllowlistError):
            allowlist.parse({"version": 1, "entries": [], "extra": 1}, TODAY)

    def test_expiry_day_itself_is_valid(self) -> None:
        allowlist.parse({"version": 1, "entries": [vendor(expires="2026-11-19")]}, TODAY)


class MatchTests(unittest.TestCase):
    def test_find_is_case_insensitive_and_tracks_use(self) -> None:
        parsed = allowlist.parse({"version": 1, "entries": [vendor(), vendor(glob="never/*.dll")]}, TODAY)
        self.assertIsNotNone(parsed.find("windows", "vendor", "Sub/VCRUNTIME140.DLL"))
        self.assertIsNone(parsed.find("windows", "unsigned-ok", "Sub/vcruntime140.dll"))
        self.assertIsNone(parsed.find("macos", "vendor", "Sub/vcruntime140.dll"))
        stale = parsed.stale_records("windows", enforce=True)
        self.assertEqual([(r.path, r.status) for r in stale], [("never/*.dll", "fail")])
        self.assertEqual(parsed.stale_records("windows", enforce=False)[0].status, "warn")
        self.assertEqual(parsed.stale_records("macos", enforce=True), [])

    def test_own_names(self) -> None:
        own = ["OrcaSlicer*.exe", "Uninstall.exe"]
        self.assertTrue(allowlist.is_own_name("payload/OrcaSlicer.exe", own))
        self.assertTrue(allowlist.is_own_name("uninstall.EXE", own))
        self.assertFalse(allowlist.is_own_name("libcurl.dll", own))


if __name__ == "__main__":
    unittest.main()
