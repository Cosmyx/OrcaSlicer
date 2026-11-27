"""Checks of the External machines section (decision 0219): the Preferences
hook lines stay where the C++ relies on them, and the French catalogue
translates every string of the feature."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PREFERENCES = REPO_ROOT / "src" / "slic3r" / "GUI" / "Preferences.cpp"
CATALOGUES = REPO_ROOT / "localization" / "cosmyx" / "external-machines"
INCLUDE = '#include "Cosmyx/ExternalMachinesPrefs.hpp" // Cosmyx'
CALL = "Cosmyx::setup_external_machines(g_sizer, item_bambu_cloud, item_enable_plugin); // Cosmyx"


def msgids(text: str) -> list[str]:
    """Non-empty msgids of a catalogue, continuation lines joined."""
    ids = []
    for block in re.findall(r'^msgid ((?:".*"\n)+)', text + "\n", flags=re.MULTILINE):
        value = "".join(re.findall(r'"(.*)"', block))
        if value:
            ids.append(value)
    return ids


class PreferencesHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = PREFERENCES.read_text(encoding="utf-8").splitlines()

    def test_include_follows_the_last_upstream_include(self) -> None:
        # Not near line 1: feat/cosmyx-cloud-server puts its include there.
        index = self.lines.index('#include "DownloadProgressDialog.hpp"')
        self.assertEqual(self.lines[index + 1], INCLUDE)

    def test_call_follows_the_plugin_version_row(self) -> None:
        calls = [i for i, line in enumerate(self.lines) if CALL in line]
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.lines[calls[0] - 1].strip(), "g_sizer->Add(item_plugin_version);")

    def test_rows_handed_over_are_built_before_the_call(self) -> None:
        call = next(i for i, line in enumerate(self.lines) if CALL in line)
        before = "\n".join(self.lines[:call])
        self.assertIn('auto item_bambu_cloud     = create_item_bambu_cloud(_L("Enable Bambu Cloud")', before)
        self.assertIn('create_item_checkbox(_L("Enable Bambu network plug-in"), "", "installed_networking")', before)

    def test_only_two_hook_lines(self) -> None:
        mine = [line for line in self.lines if "// Cosmyx" in line and ("ExternalMachines" in line or "external_machines" in line)]
        self.assertEqual(len(mine), 2)


class CatalogueTests(unittest.TestCase):
    def test_template_lists_the_feature_strings(self) -> None:
        ids = msgids((CATALOGUES / "messages.pot").read_text(encoding="utf-8"))
        self.assertIn("External machines", ids)
        self.assertTrue(any(i.startswith("This module has not been verified by Cosmyx") for i in ids))

    def test_every_language_has_the_template_msgids(self) -> None:
        template = msgids((CATALOGUES / "messages.pot").read_text(encoding="utf-8"))
        languages = sorted(p.name for p in (REPO_ROOT / "localization" / "i18n").iterdir() if p.is_dir())
        for lang in languages:
            with self.subTest(lang=lang):
                self.assertEqual(msgids((CATALOGUES / f"{lang}.po").read_text(encoding="utf-8")), template)

    def test_french_translates_every_string(self) -> None:
        text = (CATALOGUES / "fr.po").read_text(encoding="utf-8")
        self.assertIn('msgstr "Machines externes"', text)
        for block in re.split(r"\n\n", text)[1:]:
            msgstr = "".join(re.findall(r'"(.*)"', block.split("msgstr", 1)[1]))
            with self.subTest(entry=block.splitlines()[-1]):
                self.assertTrue(msgstr)


if __name__ == "__main__":
    unittest.main()
