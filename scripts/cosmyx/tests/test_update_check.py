"""Checks of the Cosmyx update check hooks (decision 0221): one call replaces
the upstream body of GUI_App::check_new_version_sf(), the update popup hides
its "stable updates only" box, and the French catalogue translates the
feature's strings."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GUI = REPO_ROOT / "src" / "slic3r" / "GUI"
CATALOGUES = REPO_ROOT / "localization" / "cosmyx" / "update-check"
INCLUDE = '#include "Cosmyx/UpdateCheckRequest.hpp" // Cosmyx'
CALL = "    Cosmyx::check_for_update(*app_config, by_user, version_info); return; // Cosmyx: Cosmyx releases only (decision 0221)"
HIDE_TAIL = " // Cosmyx: only releases are ever offered (decision 0221)"
# The integration runs on several upstream bases, whose popups build the box in
# different ways. Each known shape: (line that identifies it, anchor line the
# hook follows, hook line). Every widget of the shape is hidden.
STABLE_ONLY_SHAPES = {
    # DEV: one LabeledCheckBox carries its own label.
    "labeled checkbox": (
        'm_cb_stable_only = new LabeledCheckBox(this, _L("Check for stable updates only"));',
        "m_cb_stable_only->SetFont(Label::Body_12);",
        "    m_cb_stable_only->Hide();" + HIDE_TAIL,
    ),
    # Release tags such as v2.5.2: a bare CheckBox next to a separate Label.
    "checkbox and label": (
        "m_cb_stable_only = new CheckBox(this);",
        "stable_only_label->SetFont(Label::Body_12);",
        "    m_cb_stable_only->Hide(); stable_only_label->Hide();" + HIDE_TAIL,
    ),
}


def msgids(text: str) -> list[str]:
    """Non-empty msgids of a catalogue, continuation lines joined."""
    ids = []
    for block in re.findall(r'^msgid ((?:".*"\n)+)', text + "\n", flags=re.MULTILINE):
        value = "".join(re.findall(r'"(.*)"', block))
        if value:
            ids.append(value)
    return ids


class GuiAppHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = (GUI / "GUI_App.cpp").read_text(encoding="utf-8").splitlines()

    def test_include_follows_the_task_manager_include(self) -> None:
        # Not near line 1 nor after Downloader.hpp: other Cosmyx branches hook there.
        index = self.lines.index('#include "slic3r/GUI/TaskManager.hpp"')
        self.assertEqual(self.lines[index + 1], INCLUDE)

    def test_call_is_the_first_statement_of_the_upstream_check(self) -> None:
        index = self.lines.index("void GUI_App::check_new_version_sf(bool show_tips, int by_user)")
        self.assertEqual(self.lines[index + 1], "{")
        self.assertEqual(self.lines[index + 2], CALL)

    def test_only_two_hook_lines(self) -> None:
        mine = [l for l in self.lines if "// Cosmyx" in l and ("UpdateCheck" in l or "check_for_update" in l)]
        self.assertEqual(len(mine), 2)

    def test_every_caller_goes_through_the_hooked_function(self) -> None:
        # Startup, Help > Check for Updates and the macOS app menu all call
        # check_new_version_sf(), so the one hook covers them.
        callers = []
        for path in GUI.glob("*.cpp"):
            text = path.read_text(encoding="utf-8", errors="replace")
            callers += [path.name for _ in re.finditer(r"check_new_version_sf\(", text)]
        self.assertIn("MainFrame.cpp", callers)
        self.assertIn("GUI_App.cpp", callers)


class ReleaseNoteHookTests(unittest.TestCase):
    def test_the_stable_only_box_is_hidden_once_built(self) -> None:
        lines = (GUI / "ReleaseNote.cpp").read_text(encoding="utf-8").splitlines()
        stripped = [l.strip() for l in lines]
        shapes = [name for name, (marker, _, _) in STABLE_ONLY_SHAPES.items() if marker in stripped]
        if not shapes:
            self.skipTest("this upstream base builds no known stable-only box in ReleaseNote.cpp")
        self.assertEqual(len(shapes), 1, f"several upstream shapes found: {shapes}")
        _, anchor, hide = STABLE_ONLY_SHAPES[shapes[0]]
        self.assertIn(hide, lines, f"hook for the {shapes[0]} shape is missing")
        index = lines.index(hide)
        self.assertEqual(stripped[index - 1], anchor)
        self.assertEqual(sum("// Cosmyx" in l for l in lines), 1)


class CatalogueTests(unittest.TestCase):
    def test_template_lists_the_stealth_message(self) -> None:
        ids = msgids((CATALOGUES / "messages.pot").read_text(encoding="utf-8"))
        self.assertTrue(any(i.startswith("Checking for updates is turned off while Stealth mode is on.") for i in ids))

    def test_every_language_has_the_template_msgids(self) -> None:
        template = msgids((CATALOGUES / "messages.pot").read_text(encoding="utf-8"))
        languages = sorted(
            p.name for p in (REPO_ROOT / "localization" / "i18n").iterdir() if (p / f"OrcaSlicer_{p.name}.po").is_file()
        )
        for lang in languages:
            with self.subTest(lang=lang):
                self.assertEqual(msgids((CATALOGUES / f"{lang}.po").read_text(encoding="utf-8")), template)

    def test_french_translates_every_string(self) -> None:
        text = (CATALOGUES / "fr.po").read_text(encoding="utf-8")
        for block in re.split(r"\n\n", text)[1:]:
            msgstr = "".join(re.findall(r'"(.*)"', block.split("msgstr", 1)[1]))
            with self.subTest(entry=block.splitlines()[-1]):
                self.assertTrue(msgstr)
                self.assertIn("mode furtif", msgstr)


if __name__ == "__main__":
    unittest.main()
