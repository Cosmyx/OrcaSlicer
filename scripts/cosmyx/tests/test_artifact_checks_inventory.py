"""inventory: artifact families, the required set and the build tag in names."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import inventory  # noqa: E402

SHA = "aa9dac8f0123456789abcdef0123456789abcdef"
TAG = "2.6.0-dev-8_aa9dac8"
EXPECTATIONS = inventory.load_expectations()

# Every name build_orca.yml uploads, with the family it must land in.
NAMES = {
    f"OrcaSlicer_Windows_{TAG}_x64_portable": ("windows-portable", "x64"),
    f"OrcaSlicer_Windows_{TAG}_arm64_portable": ("windows-portable", "arm64"),
    f"OrcaSlicer_Windows_{TAG}_x64": ("windows-installer", "x64"),
    f"OrcaSlicer_Windows_{TAG}_x64_msvc": ("windows-installer", "x64"),
    f"OrcaSlicer_Windows_MSIX_{TAG}_x64": ("windows-msix", "x64"),
    f"OrcaSlicer_profile_validator_Windows_{TAG}": ("windows-validator", ""),
    f"OrcaSlicer_Mac_universal_{TAG}": ("mac-universal", ""),
    f"OrcaSlicer_Mac_arm64_{TAG}": ("mac-arm64", ""),
    f"OrcaSlicer_Mac_x86_64_{TAG}": ("mac-x86_64", ""),
    f"OrcaSlicer_profile_validator_Mac_universal_DMG_{TAG}": ("mac-validator", ""),
    f"OrcaSlicer_Mac_bundle_arm64_{SHA}": ("mac-bundle", ""),
    f"OrcaSlicer_Linux_ubuntu_2404_{TAG}": ("linux-appimage", "x86_64"),
    f"OrcaSlicer_Linux_ubuntu_2404_aarch64_{TAG}": ("linux-appimage", "aarch64"),
    f"OrcaSlicer_profile_validator_Linux_ubuntu_2404_{TAG}": ("linux-validator", ""),
}

# The same names under the CosmoSlice product name (the rename to CosmoSlice,
# package-names plan). Cosmyx builds no longer export the profile validator,
# so its names have no CosmoSlice form.
COSMO_NAMES = {name.replace("OrcaSlicer_", "CosmoSlice_", 1): spec for name, spec in NAMES.items()
               if "profile_validator" not in name}


def api(names: list[str]) -> list[dict]:
    return [{"id": index + 1, "name": name, "expired": False} for index, name in enumerate(names)]


def run(branch: str = "DEV", event: str = "workflow_dispatch", conclusion: str = "success") -> dict:
    return {"head_branch": branch, "event": event, "conclusion": conclusion, "head_sha": SHA,
            "repository": {"full_name": "Cosmyx/OrcaSlicer"}, "head_repository": {"full_name": "Cosmyx/OrcaSlicer"}}


class ClassifyTests(unittest.TestCase):
    def test_every_uploaded_name_has_its_family(self) -> None:
        for name, (family, arch) in NAMES.items():
            with self.subTest(name=name):
                found = inventory.classify(name, EXPECTATIONS)
                self.assertIsNotNone(found)
                self.assertEqual((found.family, found.arch), (family, arch))

    def test_every_cosmoslice_name_has_its_family(self) -> None:
        for name, (family, arch) in COSMO_NAMES.items():
            with self.subTest(name=name):
                found = inventory.classify(name, EXPECTATIONS)
                self.assertIsNotNone(found)
                self.assertEqual((found.family, found.arch, found.tag or TAG), (family, arch, TAG))

    def test_other_prefixes_are_unknown(self) -> None:
        for name in (f"Cosmoslice_Windows_{TAG}_x64", f"XCosmoSlice_Mac_universal_{TAG}",
                     f"CosmoSlice-Linux-flatpak_{TAG}_x86_64.flatpak"):
            with self.subTest(name=name):
                self.assertIsNone(inventory.classify(name, EXPECTATIONS))

    def test_msvc_flag_and_tag(self) -> None:
        found = inventory.classify(f"OrcaSlicer_Windows_{TAG}_x64_msvc", EXPECTATIONS)
        self.assertTrue(found.msvc)
        self.assertEqual(found.tag, TAG)

    def test_unknown_names(self) -> None:
        for name in (f"{SHA}-tests-linux-x86_64", "PDB", "generate_system_cache_Linux_ubuntu_2404_x"):
            with self.subTest(name=name):
                self.assertIsNone(inventory.classify(name, EXPECTATIONS))

    def test_inventory_groups_by_os_and_drops_ignored(self) -> None:
        found = inventory.inventory(api(list(NAMES)), EXPECTATIONS)
        self.assertEqual(len(found["windows"]), 6)
        self.assertEqual(len(found["macos"]), 4)
        self.assertEqual(len(found["linux"]), 3)
        self.assertNotIn("mac-bundle", {a.family for a in found["macos"]})


class RequiredTests(unittest.TestCase):
    def statuses(self, build: dict, names: list[str]) -> dict[str, str]:
        found = inventory.inventory(api(names), EXPECTATIONS)
        return {r.artifact: r.status for r in inventory.required_records(build, found, EXPECTATIONS)}

    def test_complete_dev_build_passes(self) -> None:
        statuses = self.statuses(run(), list(NAMES))
        self.assertEqual(sorted(statuses.values()), ["pass"] * 4)

    def test_missing_required_fails_on_dev_and_release(self) -> None:
        names = [n for n in NAMES if not n.startswith("OrcaSlicer_Mac_universal")]
        for branch in ("DEV", "release/2.6"):
            with self.subTest(branch=branch):
                statuses = self.statuses(run(branch), names)
                self.assertEqual(statuses["mac-universal"], "fail")

    def test_cosmoslice_build_without_validator_passes(self) -> None:
        statuses = self.statuses(run(), list(COSMO_NAMES))
        self.assertEqual(sorted(statuses.values()), ["pass"] * 4)

    def test_validator_absent_does_not_fail(self) -> None:
        names = [n for n in NAMES if "profile_validator" not in n]
        for build in (run(), run("release/2.6"), run(event="schedule")):
            with self.subTest(build=build):
                self.assertNotIn("fail", self.statuses(build, names).values())

    def test_mixed_prefixes_pass(self) -> None:
        names = [n if n.startswith("OrcaSlicer_Mac") else n.replace("OrcaSlicer_", "CosmoSlice_", 1)
                 for n in NAMES if "profile_validator" not in n]
        self.assertEqual(sorted(self.statuses(run(), names).values()), ["pass"] * 4)

    def test_missing_cosmoslice_required_fails(self) -> None:
        names = [n for n in COSMO_NAMES if not n.startswith("CosmoSlice_Mac_universal")]
        self.assertEqual(self.statuses(run(), names)["mac-universal"], "fail")

    def test_msvc_installer_does_not_count(self) -> None:
        names = [n for n in NAMES if n != f"OrcaSlicer_Windows_{TAG}_x64"]
        self.assertEqual(self.statuses(run(), names)["windows-installer x64"], "fail")

    def test_schedule_does_not_require_universal(self) -> None:
        names = [n for n in NAMES if not n.startswith("OrcaSlicer_Mac_universal")]
        self.assertEqual(self.statuses(run(event="schedule"), names)["mac-universal"], "skip")

    def test_skipped_outside_release_builds(self) -> None:
        for build in (run("feature/x"), run(event="pull_request"), run(conclusion="failure"), run("MIXED")):
            with self.subTest(build=build):
                self.assertEqual(set(self.statuses(build, []).values()), {"skip"})


class NamesTests(unittest.TestCase):
    def test_hash_lengths(self) -> None:
        for length in (7, 8, 9, 40):
            with self.subTest(length=length):
                name = f"OrcaSlicer_Mac_universal_2.6.0-dev-8_{SHA[:length]}"
                self.assertEqual(inventory.build_tag_hash(name, "2.6.0-dev-8", SHA), (True, SHA[:length]))

    def test_wrong_hash_or_version(self) -> None:
        self.assertFalse(inventory.build_tag_hash("OrcaSlicer_x_2.6.0-dev-8_aa9dac", "2.6.0-dev-8", SHA)[0])
        self.assertFalse(inventory.build_tag_hash("OrcaSlicer_x_2.6.0-dev-8_bbbbbbb", "2.6.0-dev-8", SHA)[0])
        self.assertFalse(inventory.build_tag_hash(f"OrcaSlicer_x_2.6.0-dev-9_{SHA[:7]}", "2.6.0-dev-8", SHA)[0])
        self.assertFalse(inventory.build_tag_hash("OrcaSlicer_x_V2.6.0", "2.6.0-dev-8", SHA)[0])

    def test_names_records(self) -> None:
        names = list(NAMES) + ["OrcaSlicer_Windows_V2.6.0_x64"]
        records = {r.artifact: r.status for r in inventory.names_records(names, "2.6.0-dev-8", SHA, EXPECTATIONS)}
        self.assertNotIn(f"OrcaSlicer_Mac_bundle_arm64_{SHA}", records)
        self.assertEqual(records["OrcaSlicer_Windows_V2.6.0_x64"], "fail")
        self.assertEqual(records[f"OrcaSlicer_Mac_universal_{TAG}"], "pass")

    def test_cosmoslice_names_records(self) -> None:
        names = list(COSMO_NAMES) + ["CosmoSlice_Windows_V2.6.0_x64", f"CosmoSlice-Linux-flatpak_{TAG}_x86_64.flatpak"]
        records = {r.artifact: r.status for r in inventory.names_records(names, "2.6.0-dev-8", SHA, EXPECTATIONS)}
        self.assertNotIn(f"CosmoSlice_Mac_bundle_arm64_{SHA}", records)
        self.assertNotIn(f"CosmoSlice-Linux-flatpak_{TAG}_x86_64.flatpak", records)
        self.assertEqual(records["CosmoSlice_Windows_V2.6.0_x64"], "fail")
        self.assertEqual(records[f"CosmoSlice_Mac_universal_{TAG}"], "pass")
        self.assertEqual(len(records), len(COSMO_NAMES))

    def test_names_skip_before_t6(self) -> None:
        records = inventory.names_records(list(NAMES), None, SHA, EXPECTATIONS)
        self.assertEqual({r.status for r in records}, {"skip"})
        self.assertIn("T6", records[0].reason)


if __name__ == "__main__":
    unittest.main()
