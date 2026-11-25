"""Checks of the Cosmyx machine hook (decision 0222): Tab.cpp carries exactly
one include and one call, and the call sits where every printer change and the
first preset load at startup reach it."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TAB = REPO_ROOT / "src" / "slic3r" / "GUI" / "Tab.cpp"
INCLUDE = '#include "Cosmyx/CosmyxMachineHook.hpp" // Cosmyx'
CALL = "Cosmyx::notify_printer_changed(); // Cosmyx"


def function_body(lines: list[str], signature: str) -> list[str]:
    """Lines of the C++ function whose definition line starts with signature."""
    start = next(i for i, line in enumerate(lines) if line.startswith(signature))
    depth, body = 0, []
    for line in lines[start:]:
        body.append(line)
        depth += line.count("{") - line.count("}")
        if depth == 0 and "{" in "".join(body):
            return body
    raise AssertionError(f"unterminated {signature}")


class TabHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = TAB.read_text(encoding="utf-8").splitlines()

    def test_include_follows_the_own_header(self) -> None:
        index = self.lines.index('#include "Tab.hpp"')
        self.assertEqual(self.lines[index + 1], INCLUDE)

    def test_call_follows_the_printer_agent_switch(self) -> None:
        calls = [i for i, line in enumerate(self.lines) if CALL in line]
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.lines[calls[0] - 1].strip(), "wxGetApp().switch_printer_agent();")
        self.assertEqual(self.lines[calls[0] - 2].strip(), "if (m_type == Preset::TYPE_PRINTER) {")

    def test_call_is_in_on_presets_changed(self) -> None:
        body = function_body(self.lines, "void Tab::on_presets_changed()")
        self.assertEqual(sum(CALL in line for line in body), 1)

    def test_startup_reaches_the_call(self) -> None:
        # GUI_App::load_current_presets() calls Tab::load_current_preset() on
        # every tab; for the printer tab that calls on_presets_changed().
        body = "\n".join(function_body(self.lines, "void Tab::load_current_preset()"))
        self.assertIn("if (m_type == Slic3r::Preset::TYPE_PRINTER) {", body)
        self.assertIn("on_presets_changed();", body)
        app = (REPO_ROOT / "src" / "slic3r" / "GUI" / "GUI_App.cpp").read_text(encoding="utf-8").splitlines()
        loader = "\n".join(function_body(app, "void GUI_App::load_current_presets("))
        self.assertIn("tab->load_current_preset();", loader)

    def test_only_two_hook_lines(self) -> None:
        mine = [line for line in self.lines if "// Cosmyx" in line and re.search(r"CosmyxMachineHook|notify_printer_changed", line)]
        self.assertEqual(len(mine), 2)


class VendorIdTests(unittest.TestCase):
    def test_vendor_id_is_one_constant(self) -> None:
        source = (REPO_ROOT / "src" / "libslic3r" / "Cosmyx" / "CosmyxMachine.cpp").read_text(encoding="utf-8")
        self.assertEqual(source.count('"Cosmyx"'), 1)
        self.assertIn('const char* const COSMYX_VENDOR_ID = "Cosmyx";', source)


if __name__ == "__main__":
    unittest.main()
