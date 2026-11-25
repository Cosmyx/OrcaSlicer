"""Tests of scripts/cosmyx/integrate/resolve.py: the known conflict kinds."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

COSMYX_DIR = Path(__file__).resolve().parents[1]
if str(COSMYX_DIR) not in sys.path:
    sys.path.insert(0, str(COSMYX_DIR))

from integrate import resolve  # noqa: E402


def conflict(ours: str, base: str, theirs: str) -> str:
    return f"<<<<<<< HEAD\n{ours}||||||| base\n{base}=======\n{theirs}>>>>>>> theirs\n"


CHANGELOG_HEAD = "## 2026-11\n\n### repo\n\n<!-- cosmyx-slot: T0 -->\n- Foundation line.\n\n"
CHANGELOG_TAIL = "### GUI\n\n<!-- cosmyx-slot: T5 -->\n"


class KindTests(unittest.TestCase):
    def test_known_paths(self) -> None:
        self.assertEqual(resolve.kind_of("CHANGELOG.md"), "changelog")
        self.assertEqual(resolve.kind_of("scripts/cosmyx/tests/test_foundation.py"), "slot-list")
        self.assertEqual(resolve.kind_of("wiki/decisions/0003-changelog-slots.md"), "slot-list")
        self.assertEqual(resolve.kind_of("cosmyx-src/branding/manifest/web.json"), "branding")
        self.assertEqual(resolve.kind_of("wiki/cosmyx/branding-assets/web.md"), "branding")

    def test_other_paths_are_unknown(self) -> None:
        for path in ("src/CHANGELOG.md", "cosmyx-src/branding/manifest/sub/x.json", "wiki/cosmyx/branding.md",
                     "cosmyx-src/branding/manifest/web.md", "wiki/decisions/0004-test-layout.md"):
            with self.subTest(path=path):
                self.assertIsNone(resolve.kind_of(path))


class ChangelogTests(unittest.TestCase):
    def test_union_of_two_new_slots_ours_first(self) -> None:
        text = CHANGELOG_HEAD + conflict(
            "<!-- cosmyx-slot: T17 -->\n- Install paths.\n  Second line.\n\n", "",
            "<!-- cosmyx-slot: T20 -->\n- Integrate recipes.\n\n") + CHANGELOG_TAIL
        merged = resolve.resolve_changelog(text)
        self.assertNotIn("<<<<<<<", merged)
        self.assertIn("<!-- cosmyx-slot: T17 -->\n- Install paths.\n  Second line.\n\n"
                      "<!-- cosmyx-slot: T20 -->\n- Integrate recipes.\n\n### GUI", merged)
        self.assertEqual(list(resolve.marker_order(merged)), ["T0", "T17", "T20", "T5"])

    def test_same_marker_keeps_both_entries_newest_first(self) -> None:
        text = conflict("<!-- cosmyx-slot: T8 -->\n- Translations.\n", "<!-- cosmyx-slot: T8 -->\n",
                        "<!-- cosmyx-slot: T8 -->\n- Fill.\n")
        merged = resolve.resolve_changelog(text)
        self.assertEqual(merged, "<!-- cosmyx-slot: T8 -->\n- Fill.\n- Translations.\n")

    def test_leading_blank_line_layout_is_kept(self) -> None:
        text = conflict("\n<!-- cosmyx-slot: T16a -->\n- A.\n", "", "\n<!-- cosmyx-slot: T19 -->\n- B.\n")
        self.assertEqual(resolve.resolve_changelog(text),
                         "\n<!-- cosmyx-slot: T16a -->\n- A.\n\n<!-- cosmyx-slot: T19 -->\n- B.\n")

    def test_crlf_file_stays_crlf(self) -> None:
        text = conflict("<!-- cosmyx-slot: T1 -->\n- A.\n", "", "<!-- cosmyx-slot: T2 -->\n- B.\n").replace("\n", "\r\n")
        merged = resolve.resolve_changelog(text)
        self.assertNotIn("\n", merged.replace("\r\n", ""))
        self.assertIn("- A.\r\n\r\n<!-- cosmyx-slot: T2 -->", merged)

    def test_both_sides_editing_a_line_is_unresolvable(self) -> None:
        text = conflict("- Foundation line, edited.\n", "- Foundation line.\n", "- Foundation line, other.\n")
        with self.assertRaises(resolve.Unresolvable):
            resolve.resolve_changelog(text)

    def test_removed_base_line_is_unresolvable(self) -> None:
        text = conflict("<!-- cosmyx-slot: T1 -->\n- A.\n", "<!-- cosmyx-slot: T9 -->\n",
                        "<!-- cosmyx-slot: T9 -->\n<!-- cosmyx-slot: T2 -->\n- B.\n")
        with self.assertRaises(resolve.Unresolvable):
            resolve.resolve_changelog(text)

    def test_heading_inside_a_block_is_unresolvable(self) -> None:
        text = conflict("<!-- cosmyx-slot: T1 -->\n- A.\n### GUI\n", "", "<!-- cosmyx-slot: T2 -->\n- B.\n")
        with self.assertRaises(resolve.Unresolvable):
            resolve.resolve_changelog(text)


class SlotListTests(unittest.TestCase):
    ORDER = {"T0": 0, "T17": 1, "T20": 2, "T1": 3, "T11f": 4, "T16": 5, "T18": 6, "T11g": 7}

    def test_python_union_follows_changelog_order(self) -> None:
        text = "SLOTS_BY_AREA = {\n" + conflict(
            '    "repo": ["T0", "T20"],\n', '    "repo": ["T0"],\n', '    "repo": ["T0", "T17"],\n') + "}\n"
        merged = resolve.resolve_slot_list(text, self.ORDER, "py")
        self.assertEqual(merged, 'SLOTS_BY_AREA = {\n    "repo": ["T0", "T17", "T20"],\n}\n')

    def test_python_several_areas(self) -> None:
        text = conflict('    "repo": ["T0", "T17"],\n    "GUI": ["T11f", "T16"],\n',
                        '    "repo": ["T0"],\n    "GUI": ["T11f"],\n',
                        '    "repo": ["T0"],\n    "GUI": ["T11f", "T11g"],\n')
        merged = resolve.resolve_slot_list(text, self.ORDER, "py")
        self.assertEqual(merged, '    "repo": ["T0", "T17"],\n    "GUI": ["T11f", "T16", "T11g"],\n')

    def test_markdown_union(self) -> None:
        text = conflict("  - `repo`: T0, T17.\n", "  - `repo`: T0.\n", "  - `repo`: T0, T20.\n")
        self.assertEqual(resolve.resolve_slot_list(text, self.ORDER, "md"), "  - `repo`: T0, T17, T20.\n")

    def test_unknown_slot_goes_last(self) -> None:
        text = conflict("  - `repo`: T0, T99.\n", "  - `repo`: T0.\n", "  - `repo`: T0, T17.\n")
        self.assertEqual(resolve.resolve_slot_list(text, self.ORDER, "md"), "  - `repo`: T0, T17, T99.\n")

    def test_removed_slot_is_unresolvable(self) -> None:
        text = conflict("  - `repo`: T17.\n", "  - `repo`: T0.\n", "  - `repo`: T0, T20.\n")
        with self.assertRaises(resolve.Unresolvable):
            resolve.resolve_slot_list(text, self.ORDER, "md")

    def test_other_code_in_the_hunk_is_unresolvable(self) -> None:
        text = conflict('    "repo": ["T0", "T20"],\n', '    "repo": ["T0"],\n', "    x = 1\n")
        with self.assertRaises(resolve.Unresolvable):
            resolve.resolve_slot_list(text, self.ORDER, "py")


class SiblingGuiSlotTests(unittest.TestCase):
    """Two sibling branches on the machine hook (T29, T31) both extend the GUI slots after T28."""

    GUI = "T5, T6, T7, T11b, T11c, T11d, T11e, T11f, T28"

    def changelog(self) -> str:
        earlier = "".join(f"<!-- cosmyx-slot: {slot} -->\n" for slot in self.GUI.split(", ")[:-1])
        base = f"### GUI\n\n{earlier}<!-- cosmyx-slot: T28 -->\n- Machine hook.\n"
        return base + conflict("\n<!-- cosmyx-slot: T29 -->\n- Models submenu.\n", "",
                               "\n<!-- cosmyx-slot: T31 -->\n- Printer connection.\n") + "\n### i18n\n"

    def test_changelog_keeps_both_slots(self) -> None:
        merged = resolve.resolve_changelog(self.changelog())
        self.assertIn("<!-- cosmyx-slot: T28 -->\n- Machine hook.\n\n<!-- cosmyx-slot: T29 -->\n- Models submenu.\n\n"
                      "<!-- cosmyx-slot: T31 -->\n- Printer connection.\n", merged)
        self.assertEqual(list(resolve.marker_order(merged))[-3:], ["T28", "T29", "T31"])

    def test_slot_lists_union_both_slots_in_changelog_order(self) -> None:
        order = resolve.marker_order(resolve.resolve_changelog(self.changelog()))
        quoted = ", ".join(f'"{slot}"' for slot in self.GUI.split(", "))
        py = conflict(f'    "GUI": [{quoted}, "T31"],\n', f'    "GUI": [{quoted}],\n',
                      f'    "GUI": [{quoted}, "T29"],\n')
        self.assertEqual(resolve.resolve_slot_list(py, order, "py"), f'    "GUI": [{quoted}, "T29", "T31"],\n')
        md = conflict(f"  - `GUI`: {self.GUI}, T31.\n", f"  - `GUI`: {self.GUI}.\n", f"  - `GUI`: {self.GUI}, T29.\n")
        self.assertEqual(resolve.resolve_slot_list(md, order, "md"), f"  - `GUI`: {self.GUI}, T29, T31.\n")


class MiscTests(unittest.TestCase):
    def test_validated_paths(self) -> None:
        manifest = {"rows": [{"path": "a.svg", "status": "validated"}, {"path": "b.svg", "status": "to-validate"}]}
        self.assertEqual(resolve.validated_paths({"x.json": json.dumps(manifest)}), {"a.svg"})

    def test_summary_names_each_hunk(self) -> None:
        text = "a\n" + conflict("x\n", "", "y\n")
        summary = resolve.summarize(text)
        self.assertEqual(len(summary), 1)
        self.assertIn("line 2", summary[0])

    def test_unterminated_conflict(self) -> None:
        with self.assertRaises(resolve.Unresolvable):
            resolve.parse("<<<<<<< HEAD\nx\n")


if __name__ == "__main__":
    unittest.main()
