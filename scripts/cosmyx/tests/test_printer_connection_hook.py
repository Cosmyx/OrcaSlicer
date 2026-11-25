"""Checks of the Cosmyx physical printer dialog hook (decision 0225): Plater.cpp
carries exactly one include and one call, and the call is the first statement
of the title bar "Connection" button handler, before upstream's dialog."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLATER = REPO_ROOT / "src" / "slic3r" / "GUI" / "Plater.cpp"
DIALOG = REPO_ROOT / "src" / "slic3r" / "GUI" / "Cosmyx" / "CosmyxPrinterConnectionDialog.cpp"
INCLUDE = '#include "Cosmyx/CosmyxPrinterConnectionDialog.hpp" // Cosmyx'
CALL = "if (Cosmyx::show_cosmyx_printer_dialog(this->GetParent())) return; // Cosmyx"
BIND = "p->m_printer_connect->Bind(wxEVT_BUTTON, [this](wxCommandEvent &e) {"


class PlaterHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = PLATER.read_text(encoding="utf-8").splitlines()

    def test_include_follows_the_own_header(self) -> None:
        self.assertEqual(self.lines[0], '#include "Plater.hpp"')
        self.assertEqual(self.lines[1], INCLUDE)

    def test_call_opens_the_connection_button_handler(self) -> None:
        calls = [i for i, line in enumerate(self.lines) if CALL in line]
        self.assertEqual(len(calls), 1)
        index = calls[0]
        self.assertEqual(self.lines[index - 1].strip(), BIND)
        self.assertEqual(self.lines[index + 1].strip(), "PhysicalPrinterDialog dlg(this->GetParent());")
        self.assertEqual(self.lines[index + 2].strip(), "dlg.ShowModal();")

    def test_only_two_hook_lines(self) -> None:
        mine = [line for line in self.lines if "// Cosmyx" in line and re.search(r"CosmyxPrinterConnection|show_cosmyx_printer_dialog", line)]
        self.assertEqual(len(mine), 2)


class DialogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = DIALOG.read_text(encoding="utf-8")

    def test_non_cosmyx_printers_keep_the_upstream_dialog(self) -> None:
        body = self.text[self.text.index("bool show_cosmyx_printer_dialog(wxWindow* parent)") :]
        first = body[body.index("{") + 1 :].strip().splitlines()
        self.assertEqual(first[0].strip(), "if (!current_printer_is_cosmyx())")
        self.assertEqual(first[1].strip(), "return false;")

    def test_only_the_four_print_host_keys_are_written(self) -> None:
        written = re.findall(r'\{"(\w+)", values\.\w+\}', self.text)
        self.assertEqual(sorted(set(written)), ["host_type", "print_host", "print_host_webui", "printhost_apikey"])
        self.assertNotRegex(self.text, r"set_key_value\(")

    def test_requests_run_off_the_ui_thread(self) -> None:
        # Every request (the connection test and the CosmOS reads) runs in a
        # detached worker that reports back through CallAfter.
        self.assertEqual(self.text.count("std::thread("), 2)
        self.assertEqual(self.text.count(").detach();"), 2)
        self.assertEqual(self.text.count("wxGetApp().CallAfter("), 2)

    def test_ends_with_the_dark_mode_pass(self) -> None:
        self.assertIn("SetSizerAndFit(sizer);", self.text)
        self.assertIn("wxGetApp().UpdateDlgDarkUI(this);", self.text)


if __name__ == "__main__":
    unittest.main()
