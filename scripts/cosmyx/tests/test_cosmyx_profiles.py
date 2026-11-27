"""Checks of the Cosmyx vendor bundle (resources/profiles/Cosmyx.json and
resources/profiles/Cosmyx/): the upstream profile tool's check passes on it,
and the choices of decision 0224 hold."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROFILES_DIR = REPO_ROOT / "resources" / "profiles"
VENDOR = "Cosmyx"
BUNDLE_DIR = PROFILES_DIR / VENDOR
INDEX = PROFILES_DIR / f"{VENDOR}.json"
TOOL = REPO_ROOT / "scripts" / "orca_profile_tool.py"


def load_presets() -> dict[str, dict]:
    """Every preset of the bundle, by name."""
    presets = {}
    for path in BUNDLE_DIR.rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        presets[data["name"]] = data
    return presets


def resolve(presets: dict[str, dict], name: str, key: str):
    """The value a preset gets for key, following its inherits chain."""
    while name:
        preset = presets[name]
        if key in preset:
            return preset[key]
        name = preset.get("inherits", "")
    return None


class ProfileToolTests(unittest.TestCase):
    def test_upstream_check_passes_on_the_bundle(self) -> None:
        result = subprocess.run(
            [sys.executable, str(TOOL), "check", "--vendor", VENDOR],
            cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        self.assertEqual(result.returncode, 0, result.stdout[-4000:] + result.stderr[-4000:])


class BundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.presets = load_presets()
        cls.index = json.loads(INDEX.read_text(encoding="utf-8"))
        cls.printers = [
            name for name, data in cls.presets.items()
            if data.get("type") == "machine" and data.get("instantiation") == "true"
        ]
        cls.models = [data for data in cls.presets.values() if data.get("type") == "machine_model"]

    def test_vendor_id_and_major_version(self) -> None:
        self.assertEqual(self.index["name"], VENDOR)
        self.assertTrue(self.index["version"].startswith("02."), self.index["version"])

    def test_eight_models_with_their_cover(self) -> None:
        self.assertEqual(len(self.models), 8)
        for model in self.models:
            with self.subTest(model=model["name"]):
                self.assertTrue((BUNDLE_DIR / f"{model['name']}_cover.png").is_file())

    def test_index_paths_exist_with_their_exact_case(self) -> None:
        # The folders are compared name by name so a case mismatch fails on
        # case-insensitive file systems too.
        for key in ("machine_model_list", "machine_list", "process_list", "filament_list"):
            for entry in self.index[key]:
                with self.subTest(sub_path=entry["sub_path"]):
                    current = BUNDLE_DIR
                    for part in Path(entry["sub_path"]).parts:
                        self.assertIn(part, {child.name for child in current.iterdir()})
                        current = current / part

    def test_no_preset_name_translation_folder(self) -> None:
        self.assertFalse(any(child.name.lower() == "i18n" for child in BUNDLE_DIR.iterdir()))

    def test_no_cosmyx_bed_type(self) -> None:
        for name, data in self.presets.items():
            with self.subTest(preset=name):
                self.assertFalse([key for key in data if key.startswith("cosmyx_textured_bed")])
        # default_bed_type is a printer key: on a machine_model it has no effect.
        for printer in self.printers:
            with self.subTest(printer=printer):
                self.assertEqual(resolve(self.presets, printer, "default_bed_type"), "Textured PEI Plate")
        for model in self.models:
            with self.subTest(model=model["name"]):
                self.assertNotIn("default_bed_type", model)

    def test_every_printer_resolves_its_defaults(self) -> None:
        for printer in self.printers:
            with self.subTest(printer=printer):
                process = resolve(self.presets, printer, "default_print_profile")
                self.assertIn(process, self.presets)
                self.assertIn(printer, resolve(self.presets, process, "compatible_printers"))
                filaments = resolve(self.presets, printer, "default_filament_profile")
                self.assertTrue(filaments)
                for filament in filaments:
                    self.assertIn(filament, self.presets)
                    self.assertIn(printer, self.presets[filament]["compatible_printers"])

    def test_every_compatible_printer_exists(self) -> None:
        for name, data in self.presets.items():
            for printer in data.get("compatible_printers", []):
                with self.subTest(preset=name, printer=printer):
                    self.assertIn(printer, self.printers)

    def test_open_filaments_list_every_printer(self) -> None:
        # Filaments open to every printer list them all: upstream forbids an
        # empty compatible_printers on an instantiated vendor filament.
        for name, data in self.presets.items():
            if data.get("type") != "filament" or data.get("instantiation") != "true":
                continue
            with self.subTest(filament=name):
                self.assertTrue(data.get("compatible_printers"))

    def test_sndt_defaults_to_the_common_standard_process(self) -> None:
        printer = "Cosmyx SuperNova Double Tete 0.4 nozzle"
        self.assertEqual(resolve(self.presets, printer, "default_print_profile"), "0.20mm Standard @Cosmyx Common")

    def test_no_ip_address_in_the_bundle(self) -> None:
        # Bundle versions (NN.NN.NN.NN) are dotted quads too, so the version
        # value is left out of the scan.
        pattern = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
        for path in [INDEX, *BUNDLE_DIR.rglob("*.json")]:
            text = re.sub(r'"version":\s*"[^"]*"', "", path.read_text(encoding="utf-8"))
            with self.subTest(file=path.name):
                self.assertIsNone(pattern.search(text))


if __name__ == "__main__":
    unittest.main()
