"""Checks of the Cosmyx models submenu gating (decision 0223): the submenu
follows the Cosmyx machine flag through the machine hook alone, with no
upstream line beyond the models menu's own three GUI_Factories.cpp hooks."""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FACTORIES = REPO_ROOT / "src" / "slic3r" / "GUI" / "GUI_Factories.cpp"
MENU = REPO_ROOT / "src" / "slic3r" / "GUI" / "Cosmyx" / "CosmyxModelsMenu.cpp"
HANDY = 'append_submenu({menu}, sub_menu_handy, wxID_ANY, _L("Add Handy models"), "", "menu_add_part",'


class FactoriesHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = FACTORIES.read_text(encoding="utf-8").splitlines()

    def test_only_the_models_menu_hooks(self) -> None:
        mine = [line.strip() for line in self.lines if "// Cosmyx" in line]
        self.assertEqual(mine, [
            '#include "Cosmyx/CosmyxModelsMenu.hpp" // Cosmyx',
            "Cosmyx::append_models_submenu(&m_default_menu, m_parent); // Cosmyx",
            "Cosmyx::append_models_submenu(menu, m_parent); // Cosmyx",
        ])

    def test_each_call_follows_the_handy_models_item(self) -> None:
        # The gating saves the item appended just before the call as the
        # anchor it reinserts after; that item must be "Add Handy models".
        for menu, call in (("&m_default_menu", "Cosmyx::append_models_submenu(&m_default_menu, m_parent); // Cosmyx"),
                           ("menu", "Cosmyx::append_models_submenu(menu, m_parent); // Cosmyx")):
            with self.subTest(menu=menu):
                index = next(i for i, line in enumerate(self.lines) if line.strip() == call)
                self.assertEqual(self.lines[index - 2].strip(), HANDY.format(menu=menu))
                self.assertEqual(self.lines[index - 1].strip(), "[]() {return true; }, m_parent);")


class GatingSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = MENU.read_text(encoding="utf-8")

    def test_menu_reads_and_follows_the_machine_flag(self) -> None:
        self.assertIn('#include "CosmyxMachineHook.hpp"', self.text)
        self.assertIn("subscribe_printer_is_cosmyx(apply_printer_is_cosmyx);", self.text)
        self.assertIn("if (current_printer_is_cosmyx())", self.text)

    def test_reinsertion_uses_the_saved_slot(self) -> None:
        self.assertIn("slot_insert_position(ids, slot.anchor_id, slot.saved_index)", self.text)
        self.assertIn("build_models_submenu(menu, slot.parent, int(pos))", self.text)

    def test_items_are_found_by_id(self) -> None:
        self.assertNotIn("FindItem(_", self.text)
        self.assertIn("FindChildItem(slot.item_id)", self.text)

    def test_menus_are_forgotten_with_their_window(self) -> None:
        self.assertIn("parent->Bind(wxEVT_DESTROY", self.text)


if __name__ == "__main__":
    unittest.main()
