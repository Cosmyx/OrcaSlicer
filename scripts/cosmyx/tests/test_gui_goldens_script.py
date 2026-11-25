"""tests/cosmyx/gui/script.json against the sources: every NativeCommands
catalog key is classified (decision 0173), every surface id is valid, the
fixtures exist and the Preferences tabs match the upstream enum."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GUI = ROOT / "src" / "slic3r" / "GUI"
SCRIPT = ROOT / "tests" / "cosmyx" / "gui" / "script.json"
CLASSES = {"dialog", "view", "toggle", "any", "skip"}
ACTIONS = {"tab", "command", "prefs_tab", "settings", "load", "reset", "select_all", "context_menu", "menu", "wait", "slice",
           "copy_gcode", "close_tips"}
SURFACE = re.compile(r"^[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*$")


def slug(text: str) -> str:
    return "-".join(part for part in re.split(r"[^a-z0-9]+", text.lower()) if part)


def catalog_keys() -> list[str]:
    """Keys NativeCommands::catalog() builds, read from the source."""
    text = (GUI / "NativeCommands.cpp").read_text(encoding="utf-8")
    body = text[text.index("build_command_catalog()"):]
    keys = re.findall(r'\badd(?:_with_icon)?\(\s*"([a-z0-9_]+)"(?!\s*\+)', body)
    keys += re.findall(r'\{"(view_[a-z]+)",\s*"[a-z]+",', body)
    keys += re.findall(r'\badd_primitive\("([a-z0-9_]+)"', body)
    if '"add_handy_" + std::string(handy[i].key)' in body:
        factories = (GUI / "GUI_Factories.cpp").read_text(encoding="utf-8")
        table = factories[factories.index("MenuFactory::handy_models()"):]
        table = table[:table.index("};")]
        keys += ["add_handy_" + key for key in re.findall(r'\{"([a-z0-9_]+)",\s*L\(', table)]
    return keys


class ScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.script = json.loads(SCRIPT.read_text(encoding="utf-8"))
        cls.rules = cls.script["menu_items"]
        cls.keys = catalog_keys()

    def test_header(self) -> None:
        self.assertEqual(self.script["protocol"], 1)
        self.assertEqual(self.script["language"], "en_US")  # decision 0176: English only
        self.assertEqual(self.script["window"]["client_size"], [1280, 800])

    def test_catalog_is_read_from_the_source(self) -> None:
        self.assertGreater(len(self.keys), 90)
        self.assertEqual(len(self.keys), len(set(self.keys)))
        for key in ("slice_and_preview", "help_about", "view_iso", "add_primitive_torus", "add_handy_3dbenchy",
                    "install_local_plugin"):
            self.assertIn(key, self.keys)

    def test_every_catalog_key_is_classified(self) -> None:
        self.assertEqual(sorted(set(self.keys) - set(self.rules)), [], "unclassified commands")

    def test_no_rule_names_a_removed_command(self) -> None:
        self.assertEqual(sorted(set(self.rules) - set(self.keys)), [], "stale rules")

    def test_rules_are_well_formed(self) -> None:
        for key, rule in self.rules.items():
            with self.subTest(key=key):
                self.assertIn(rule["class"], CLASSES)
                if rule["class"] == "skip":
                    self.assertTrue(rule.get("reason"))
                else:
                    self.assertRegex(rule.get("section", ""), r"^[0-9]{2}$")
                if "revert" in rule:
                    self.assertIn(rule["revert"], self.rules)

    def test_generated_and_literal_ids_are_valid_and_unique(self) -> None:
        ids = [step["id"] for step in self.script["steps"] if "id" in step]
        ids += [f"{rule['section']}-{slug(key)}" for key, rule in self.rules.items() if rule.get("section")]
        ids += [f"99-{slug(key)}" for key, rule in self.rules.items() if not rule.get("section")]
        ids += [f"40-preferences-{tab}" for tab in ("general", "files", "behaviour", "control", "graphics", "online")]
        for surface in ids:
            self.assertRegex(surface, SURFACE)
        self.assertEqual(len(ids), len(set(ids)))

    def test_steps_use_known_actions(self) -> None:
        for step in self.script["steps"]:
            for action in step.get("do", []) + step.get("after", []):
                with self.subTest(step=step.get("id"), action=action):
                    self.assertEqual(len(set(action) - {"param"}), 1)
                    self.assertIn(next(iter(set(action) - {"param"})), ACTIONS)

    def test_sections_are_all_expanded(self) -> None:
        generated = {step.get("section") for step in self.script["steps"] if step.get("generate") == "commands"}
        used = {rule["section"] for rule in self.rules.values() if rule.get("section")}
        self.assertEqual(used - generated, set(), "rules in a section no generator expands")
        kinds = [step.get("generate") for step in self.script["steps"] if "generate" in step]
        for kind in ("menus", "prefs", "settings"):
            self.assertIn(kind, kinds)

    def test_slice_steps_are_present(self) -> None:
        ids = [step.get("id") for step in self.script["steps"]]
        for surface in ("00-start", "90-slice-preview", "90-slice-layer", "90-slice-gcode", "70-context-menu"):
            self.assertIn(surface, ids)

    def test_fixtures_ship_with_the_app(self) -> None:
        for name, value in self.script["fixtures"].items():
            with self.subTest(fixture=name):
                self.assertTrue(value.startswith("resources:"))
                self.assertTrue((ROOT / "resources" / value[len("resources:"):]).is_file())

    def test_preferences_tabs_follow_the_upstream_enum(self) -> None:
        header = (GUI / "Preferences.hpp").read_text(encoding="utf-8")
        enum = re.search(r"enum class PreferencesTab \{([^}]*)\}", header).group(1)
        names = [name.strip().lower() for name in enum.split(",") if name.strip()]
        self.assertEqual(names, ["general", "files", "behaviour", "control", "graphics", "online"])

    def test_main_tabs_exist(self) -> None:
        header = (GUI / "MainFrame.hpp").read_text(encoding="utf-8")
        tab_ids = set(re.findall(r'#define TAB_ID_[A-Z_]+\s+"([a-z_]+)"', header))
        for step in self.script["steps"]:
            for action in step.get("do", []):
                if "tab" in action:
                    self.assertIn(action["tab"], tab_ids)


if __name__ == "__main__":
    unittest.main()
