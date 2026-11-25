"""Tests of the colour stage (scripts/cosmyx/branding/colours.py): the hex
rewrite rule, the tuple recogniser and its literal rows, the snippets, the
leftover guard, the WCAG contrast, the committed colours.json and a real-tree
apply on a scratch copy of this repository."""

from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from branding_fixture import (
    RELEASE,
    REPO_ROOT,
    TreeCase,
    apply_module,
    branding,
    copy_real_tree,
    read,
    snapshot,
    to_crlf,
    write,
)
from branding import colours, find_hexes, in_family

PLUGINS = {"colours": [colours]}

# The branding mode of this run (decision 0122): the cosmyx-prepare action
# exports COSMYX_BRAND_MODE, tolerant only when the tree's upstream base is not
# DEV, so the real-tree tests check this checkout the way its build brands it.
MODE_ENV = "COSMYX_BRAND_MODE"
REAL_TREE_ENV = {MODE_ENV: os.environ.get(MODE_ENV, "")}
TOLERANT = REAL_TREE_ENV[MODE_ENV].strip() == "tolerant"


def present_in(root: Path, row: dict) -> bool:
    """True when the file of a literal row exists and holds its text."""
    path = root / row["file"]
    return path.is_file() and row["find"] in path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
# The default filament colour fallbacks (decision 0128).
PRESET_BUNDLE = "src/libslic3r/PresetBundle.cpp"
FILAMENT_GREY = "#242323"
FILAMENT_FIND = 'filament_colors.resize(filament_presets.size(), "#26A69A");'
FILAMENT_REPLACE = f'filament_colors.resize(filament_presets.size(), "{FILAMENT_GREY}");'
WIDGET = "src/slic3r/GUI/Widget.cpp"
CSS = "resources/web/css/global.css"

TABLE = {
    "schema": 1,
    "palette": {"brand": "#8000FF", "brand_dark_screen": "#A472F5", "lavender": "#B4B9DD"},
    "mappings": [
        {"from": "#009688", "to": "#8000FF", "role": "light base", "source": "user", "status": "to-validate"},
        {"from": "#00675B", "to": "#A472F5", "role": "dark base", "source": "user", "status": "to-validate"},
        {"from": "#283232", "to": "#A472F5", "role": "dark tint", "source": "derived", "status": "to-validate"},
    ],
    "ignore": ["#00AE42", "#1F8EEA"],
    "scopes": ["src/slic3r/*.cpp", "!src/slic3r/GUI/Cosmyx/*", "resources/web/*.css"],
    "literals": [
        {"file": WIDGET, "find": "wxColour(0, 150, 136", "replace": "wxColour(128, 0, 255", "count": 1, "reason": "tuple #009688 -> #8000FF"}
    ],
    "snippets": [],
    "allow_residue": [],
}


class HexRewriteTest(unittest.TestCase):
    table = {"#009688": "#8000FF", "#00675B": "#A472F5"}

    def rewrite(self, text: str) -> str:
        return colours.rewrite_hex(text.encode("utf-8"), self.table)[0].decode("utf-8")

    def test_any_case_becomes_uppercase(self) -> None:
        self.assertEqual(self.rewrite("a #009688 b #00675b c"), "a #8000FF b #A472F5 c")

    def test_eight_digit_colour_keeps_its_alpha(self) -> None:
        self.assertEqual(self.rewrite("fill:#009688cc;"), "fill:#8000FFcc;")

    def test_longer_or_shorter_hex_runs_are_not_colours(self) -> None:
        for text in ("#0096881", "#009688ABC", "#00968", "0x009688"):
            self.assertEqual(self.rewrite(text), text)

    def test_references_and_base64_are_untouched(self) -> None:
        for text in (
            '<a href="#009688">',
            '<use xlink:href="#009688"/>',
            "fill: url(#009688);",
            "fill: url( '#009688');",
            "data:image/png;base64,MDA5Njg4IzAwOTY4OA==",
        ):
            self.assertEqual(self.rewrite(text), text)

    def test_url_fragments_and_character_references_are_untouched(self) -> None:
        for text in (
            '<a href="https://example.org/page#009688">',
            "see https://example.org/page.html#009688 for details",
            "<p>&#009688;</p>",
        ):
            self.assertEqual(self.rewrite(text), text)
            self.assertEqual(find_hexes(text), [])

    def test_colours_next_to_a_url_are_still_colours(self) -> None:
        """Only the URL itself is protected: a colour after the link, a quote
        or whitespace away, is rewritten."""
        self.assertEqual(
            self.rewrite('<a href="https://example.org/x" style="color:#009688">'),
            '<a href="https://example.org/x" style="color:#8000FF">',
        )
        self.assertEqual(self.rewrite("https://example.org/x #009688"), "https://example.org/x #8000FF")
        self.assertEqual(self.rewrite("a&b:#009688"), "a&b:#8000FF")

    def test_unmapped_and_ignored_colours_stay(self) -> None:
        self.assertEqual(self.rewrite("#00AE42 #26A69A #FFFFFF"), "#00AE42 #26A69A #FFFFFF")

    def test_counts_and_line_endings(self) -> None:
        data, counts = colours.rewrite_hex(b'"#009688"\r\n"#009688"\r\n#00675B', self.table)
        self.assertEqual(data, b'"#8000FF"\r\n"#8000FF"\r\n#A472F5')
        self.assertEqual(counts, {"#009688": 2, "#00675B": 1})

    def test_bytes_outside_utf8_survive(self) -> None:
        data, _ = colours.rewrite_hex(b"\xb7\xa2 #009688 \xff", self.table)
        self.assertEqual(data, b"\xb7\xa2 #8000FF \xff")


class TupleTest(unittest.TestCase):
    table = {"#009688": "#8000FF", "#26A69A": "#A472F5", "#00675B": "#A472F5"}

    def proposals(self, text: str) -> dict:
        found = {}
        for match, rgb in colours.find_tuples(text):
            source = colours.mapped_colour(rgb, self.table)
            if source:
                found[match.group(0)] = colours.rewrite_tuple(match, self.table[source], rgb[3])
        return found

    def test_integer_forms(self) -> None:
        self.assertEqual(
            self.proposals("wxColour(0, 150, 136) IM_COL32(0,150,136, 255) rgba(0, 150, 136, .18)"),
            {
                "wxColour(0, 150, 136": "wxColour(128, 0, 255",
                "IM_COL32(0,150,136": "IM_COL32(128,0,255",
                "rgba(0, 150, 136": "rgba(128, 0, 255",
            },
        )

    def test_hex_byte_forms_keep_their_case(self) -> None:
        self.assertEqual(self.proposals("wxColour(0x00, 0x96, 0x88)"), {"wxColour(0x00, 0x96, 0x88": "wxColour(0x80, 0x00, 0xFF"})
        self.assertEqual(self.proposals("wxColour(0x26, 0xa6, 0x9a)"), {"wxColour(0x26, 0xa6, 0x9a": "wxColour(0xa4, 0x72, 0xf5"})

    def test_float_forms_match_within_rounding(self) -> None:
        self.assertEqual(
            self.proposals("ImVec4(0.00f, 0.59f, 0.53f, 1.0f) ImVec4(0, 0.588, 0.533, 1) ImVec4(0.f, .59f, .53f, 1)"),
            {
                "ImVec4(0.00f, 0.59f, 0.53f": "ImVec4(0.50f, 0.00f, 1.00f",
                "ImVec4(0, 0.588, 0.533": "ImVec4(0.502, 0.000, 1.000",
                "ImVec4(0.f, .59f, .53f": "ImVec4(0.502f, 0.00f, 1.00f",
            },
        )

    def test_ratio_forms_keep_their_notation(self) -> None:
        self.assertEqual(
            self.proposals("x = { 38 / 255.f, 166 / 255.f, 154 / 255.f, 1.f }; return {0.0f, 150.f / 255.0f, 136.0f / 255};"),
            {
                "= { 38 / 255.f, 166 / 255.f, 154 / 255.f": "= { 164 / 255.f, 114 / 255.f, 245 / 255.f",
                "return {0.0f, 150.f / 255.0f, 136.0f / 255": "return {0.502f, 0.f / 255.0f, 255.0f / 255",
            },
        )

    def test_rewritten_tuple_reads_back_as_the_target(self) -> None:
        for text in ("ImVec4(0.00f, 0.59f, 0.53f, 1)", "= {0.f, 103 / 255.f, 91 / 255.f, 1}", "wxColour(38, 166, 154)"):
            for match, rgb in colours.find_tuples(text):
                target = self.table[colours.mapped_colour(rgb, self.table)]
                again = list(colours.find_tuples(colours.rewrite_tuple(match, target, rgb[3]) + ")"))
                self.assertTrue(colours.close_to(again[0][1], target, 2), (text, again[0][1], target))

    def test_non_colours_are_not_tuples(self) -> None:
        for text in ("Vec3d(0, 150, 136)", "wxColour(0, 300, 136)", "ImVec4(0, 2, 3, 1.f)", "foo(0, 150, 136)"):
            self.assertEqual(list(colours.find_tuples(text)), [], text)

    def test_integer_tuples_are_exact(self) -> None:
        self.assertEqual(self.proposals("wxColour(0, 151, 136)"), {})


class ContrastTest(unittest.TestCase):
    def test_wcag_reference_values(self) -> None:
        self.assertEqual(colours.contrast("#FFFFFF", "#000000"), 21.0)
        self.assertEqual(colours.contrast("#777777", "#777777"), 1.0)
        self.assertEqual(colours.contrast("#000000", "#FFFFFF"), colours.contrast("#FFFFFF", "#000000"))

    def test_brand_pairs(self) -> None:
        self.assertEqual(colours.contrast("#8000FF", "#FFFFFF"), 6.25)
        self.assertEqual(colours.contrast("#A472F5", "#1C1C1F"), 5.10)
        self.assertEqual(colours.contrast("#FFFFFF", "#A472F5"), 3.33)
        self.assertEqual(colours.contrast("#8000FF", "#1C1C1F"), 2.72)

    def test_rows_report_both_backgrounds(self) -> None:
        rows = colours.contrast_rows(TABLE)
        self.assertEqual(len(rows), 3)
        self.assertEqual(
            set(rows[0]), {"from", "to", "role", "from_on_FFFFFF", "from_on_1C1C1F", "to_on_FFFFFF", "to_on_1C1C1F"}
        )
        self.assertEqual(rows[0]["to_on_FFFFFF"], 6.25)

    def test_blends(self) -> None:
        self.assertEqual(colours.blend("#8000FF", "#FFFFFF", 0.25), "#DFBFFF")
        self.assertEqual(colours.blend("#8000FF", "#FFFFFF", 0.10), "#F2E6FF")
        self.assertEqual(colours.blend("#8000FF", "#FFFFFF", 1.0), "#8000FF")


class TableTest(unittest.TestCase):
    def problems(self, **changes) -> list:
        table = copy.deepcopy(TABLE)
        table.update(changes)
        return colours.table_problems(table)

    def row(self, **changes) -> list:
        row = dict(TABLE["mappings"][0], **changes)
        return self.problems(mappings=[row])

    def test_sample_table_is_valid(self) -> None:
        self.assertEqual(colours.table_problems(TABLE), [])

    def test_bad_rows(self) -> None:
        self.assertTrue(self.row(**{"from": "#009688aa"}))
        self.assertTrue(self.row(**{"from": "#00968g"}))
        self.assertTrue(self.row(to="#8000ff"))
        self.assertTrue(self.row(to="#123456"))
        self.assertTrue(self.row(source="guess"))
        self.assertTrue(self.row(status="approved"))
        self.assertTrue(self.row(role=""))
        self.assertTrue(self.row(**{"from": "#00AE42"}))
        self.assertTrue(self.problems(mappings=[TABLE["mappings"][0]] * 2))

    def test_bad_palette(self) -> None:
        self.assertEqual(self.problems(palette=["#8000FF", "#A472F5"]), [])
        self.assertTrue(self.problems(palette={"brand": "#8000ff", "dark": "#A472F5"}))
        self.assertTrue(self.problems(palette=["#8000FF", 42]))
        self.assertTrue(self.problems(palette="#8000FF"))

    def test_bad_snippets(self) -> None:
        good = {"file": WIDGET, "anchor": "a", "insert": "b", "count": 1, "reason": "r"}
        self.assertEqual(self.problems(snippets=[good]), [])
        self.assertTrue(self.problems(snippets=[dict(good, insert="b\nc")]))
        self.assertTrue(self.problems(snippets=[dict(good, count=0)]))
        self.assertTrue(self.problems(snippets=[{"file": WIDGET}]))


class ColourStageTest(TreeCase):
    """The plugin inside the engine pipeline, on the fake tree."""

    def setUp(self) -> None:
        super().setUp()
        self.table = copy.deepcopy(TABLE)
        self.save()

    def save(self) -> None:
        self.write_json(branding.COLOURS_FILE, self.table)

    def run_apply(self, env=None):
        return self.apply(env=env, plugins=PLUGINS)

    def test_apply_rewrites_and_reports(self) -> None:
        code, lines = self.run_apply()
        self.assertEqual(code, 0, lines)
        self.assertEqual(read(self.root, WIDGET), b'auto c = wxColour(128, 0, 255); // brand\nauto h = "#8000FF";\n')
        self.assertEqual(read(self.root, CSS), b":root { --main-color: #8000FF; }\n")
        report = json.loads(read(self.root, branding.REPORT_FILE))
        plugin = report["stages"]["colours"]["plugin"]
        self.assertEqual(plugin["rewritten_files"], 2)
        self.assertEqual(plugin["replacements"], {"#009688": 2})
        self.assertEqual(len(plugin["contrast"]), 3)

    def test_revert_is_exact(self) -> None:
        before = snapshot(self.root)
        self.assertEqual(self.run_apply()[0], 0)
        apply_module.revert(self.root)
        self.assertEqual(snapshot(self.root), before)

    def test_out_of_scope_files_are_untouched(self) -> None:
        write(self.root, "src/slic3r/GUI/Cosmyx/Mine.cpp", '"#009688"\n')
        write(self.root, "src/libslic3r/PresetBundle.cpp", '"#009688"\n')
        self.assertEqual(self.run_apply()[0], 0)
        self.assertEqual(read(self.root, "src/slic3r/GUI/Cosmyx/Mine.cpp"), b'"#009688"\n')
        self.assertEqual(read(self.root, "src/libslic3r/PresetBundle.cpp"), b'"#009688"\n')

    def test_ignored_green_is_neither_rewritten_nor_reported(self) -> None:
        write(self.root, "src/slic3r/GUI/Green.cpp", 'auto g = "#00AE42"; auto t = wxColour(0, 174, 66);\n')
        self.assertEqual(self.run_apply()[0], 0)
        self.assertEqual(read(self.root, "src/slic3r/GUI/Green.cpp"), b'auto g = "#00AE42"; auto t = wxColour(0, 174, 66);\n')

    def test_new_teal_hex_shade_is_caught(self) -> None:
        write(self.root, "src/slic3r/GUI/New.cpp", 'auto n = "#00A090";\n')
        code, lines = self.run_apply()
        self.assertEqual(code, 1)
        self.assertTrue(any("G5" in line and "#00A090" in line for line in lines), lines)
        self.assertEqual(read(self.root, WIDGET).count(b"#009688"), 1)

    def test_new_teal_tuple_is_caught_and_allowed_only_with_its_exact_count(self) -> None:
        write(self.root, "src/slic3r/GUI/New.cpp", "auto n = ImVec4(0.f, .63f, .57f, 1.f);\n")
        code, lines = self.run_apply()
        self.assertEqual(code, 1)
        self.assertTrue(any("G5" in line and "RGB(0, 161, 145)" in line for line in lines), lines)
        self.table["allow_residue"] = [{"file": "src/slic3r/GUI/New.cpp", "match": "rgb(0, 161, 145)", "count": 2, "reason": "test"}]
        self.save()
        self.assertEqual(self.run_apply()[0], 1)
        self.table["allow_residue"][0]["count"] = 1
        self.save()
        self.assertEqual(self.run_apply()[0], 0)

    def test_teal_integer_literal_is_caught(self) -> None:
        write(self.root, "src/slic3r/GUI/New.cpp", "StateColor c(0x00A090);\n")
        code, lines = self.run_apply()
        self.assertEqual(code, 1)
        self.assertTrue(any("0X00A090" in line for line in lines), lines)

    def test_mapped_colour_outside_the_family_is_caught(self) -> None:
        self.assertFalse(in_family("#283232"))
        write(self.root, "src/slic3r/GUI/Dark.cpp", 'auto d = wxColour(40, 50, 50);\n')
        code, lines = self.run_apply()
        self.assertEqual(code, 1)
        self.assertTrue(any("RGB(40, 50, 50)" in line for line in lines), lines)
        write(self.root, "src/slic3r/GUI/Dark.cpp", 'auto d = "#283232";\n')
        self.assertEqual(self.run_apply()[0], 0)
        self.assertEqual(read(self.root, "src/slic3r/GUI/Dark.cpp"), b'auto d = "#A472F5";\n')

    def test_stale_literal_refuses_and_writes_nothing(self) -> None:
        self.table["literals"][0]["count"] = 2
        self.save()
        before = snapshot(self.root)
        code, lines = self.run_apply()
        self.assertEqual(code, 1)
        self.assertTrue(any("found 1 time(s), expected 2" in line for line in lines), lines)
        self.assertEqual({k: v for k, v in snapshot(self.root).items()}, before)

    def test_snippet_is_inserted_after_its_anchor(self) -> None:
        self.table["snippets"] = [
            {"file": WIDGET, "anchor": "auto h = \"#009688\";", "insert": "auto k = 1; // Cosmyx", "count": 1, "reason": "test"}
        ]
        self.save()
        self.assertEqual(self.run_apply()[0], 0)
        self.assertEqual(read(self.root, WIDGET), b'auto c = wxColour(128, 0, 255); // brand\nauto h = "#8000FF";\nauto k = 1; // Cosmyx\n')

    def test_missing_anchor_refuses(self) -> None:
        self.table["snippets"] = [{"file": WIDGET, "anchor": "no such line", "insert": "x", "count": 1, "reason": "test"}]
        self.save()
        before = snapshot(self.root)
        code, lines = self.run_apply()
        self.assertEqual(code, 1)
        self.assertTrue(any("no such line" in line for line in lines), lines)
        self.assertEqual(snapshot(self.root), before)

    def test_invalid_table_refuses(self) -> None:
        self.table["mappings"][0]["to"] = "#8000ff"
        self.save()
        code, lines = self.run_apply()
        self.assertEqual(code, 1)
        self.assertTrue(any("uppercase" in line for line in lines), lines)

    def test_unvalidated_mappings_warn_on_development_and_fail_release(self) -> None:
        code, lines = self.run_apply()
        self.assertEqual(code, 0)
        self.assertTrue(any(line.startswith("warning: P") and "colour mapping" in line for line in lines), lines)
        for row in self.table["mappings"]:
            row["status"] = "validated"
        self.save()
        findings = colours.guards(self.ctx(env=RELEASE, plugins=PLUGINS), "pre")
        self.assertFalse([f for f in findings if "colour mapping" in f.message])
        self.table["mappings"][0]["status"] = "to-validate"
        self.save()
        findings = colours.guards(self.ctx(env=RELEASE, plugins=PLUGINS), "pre")
        self.assertTrue([f for f in findings if f.level == "error" and "colour mapping" in f.message])

    def test_literal_proposals_match_the_tree(self) -> None:
        rows = colours.propose_literals(self.root, self.table)
        self.assertEqual(rows, [dict(self.table["literals"][0], reason="tuple #009688 -> #8000FF")])
        self.assertEqual(colours.literal_rows(self.root, self.table), rows)

    def test_cli_writes_nothing_without_write(self) -> None:
        before = snapshot(self.root)
        lines = []
        self.assertEqual(colours.main(["candidates"], root=self.root, out=lines.append), 0)
        self.assertIn("#009688   #8000FF", lines[0])
        self.assertIn("#DFBFFF", lines[0])
        self.assertEqual(colours.main(["literals"], root=self.root, out=lines.append), 0)
        self.assertEqual(snapshot(self.root), before)
        self.table["literals"].append({"file": WIDGET, "find": "c =", "replace": "c =", "count": 1, "reason": "kept by hand"})
        self.save()
        self.assertEqual(colours.main(["literals", "--write"], root=self.root, out=lines.append), 0)
        written = branding.load_json(self.root / branding.COLOURS_FILE)["literals"]
        self.assertEqual([row["reason"] for row in written], ["kept by hand", "tuple #009688 -> #8000FF"])


class CommittedTableTest(unittest.TestCase):
    """The committed colours.json is valid and its literal rows are current."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.table = branding.load_json(REPO_ROOT / branding.COLOURS_FILE)

    def test_table_is_valid_and_canonical(self) -> None:
        self.assertEqual(colours.table_problems(self.table), [])
        # Line endings aside: a Windows checkout (core.autocrlf) holds it in CRLF.
        self.assertTrue(branding.same_text(REPO_ROOT / branding.COLOURS_FILE, branding.dump_json(self.table)))

    def test_user_colours_and_sources(self) -> None:
        by_source = {row["from"]: row for row in self.table["mappings"]}
        for source, target in (
            ("#009688", "#8000FF"),
            ("#00675B", "#A472F5"),
            ("#223C3C", "#382D43"),
            # Hover teal of the one-layer icons, chosen by the user (decision 0127).
            ("#33ABA1", "#A472F5"),
        ):
            self.assertEqual((by_source[source]["to"], by_source[source]["source"]), (target, "user"))
        self.assertEqual({by_source[c]["to"] for c in ("#52C7B8", "#4DB6AC")}, {"#B4B9DD"})
        self.assertTrue(all(row["status"] in colours.STATUSES for row in self.table["mappings"]))

    def test_every_mapping_is_validated(self) -> None:
        # The user approved the whole colour table on 2026-11-19 (decision 0127).
        self.assertEqual([row["from"] for row in self.table["mappings"] if row["status"] != "validated"], [])

    def test_literal_rows_are_current(self) -> None:
        expected = self.table["literals"]
        if TOLERANT:
            # An older upstream base lacks some rows' files or texts; apply
            # skips those with a warning, the rest must still be current.
            expected = [row for row in expected if present_in(REPO_ROOT, row)]
        self.assertEqual(colours.literal_rows(REPO_ROOT, self.table), expected)

    def test_scopes_follow_the_plan(self) -> None:
        scopes = self.table["scopes"]
        self.assertIn("!src/slic3r/GUI/Cosmyx/*", scopes)
        libslic3r = [scope for scope in scopes if scope.startswith("src/libslic3r")]
        self.assertEqual(libslic3r, ["src/libslic3r/Color.hpp"])

    def test_default_filament_colour_rows(self) -> None:
        # The default filament colour is the user's dark grey (decision 0128):
        # one row on the two fallbacks of PresetBundle.cpp, nothing else there.
        rows = [row for row in self.table["literals"] if row["file"] == PRESET_BUNDLE]
        self.assertEqual([(row["find"], row["replace"], row["count"]) for row in rows], [(FILAMENT_FIND, FILAMENT_REPLACE, 2)])
        self.assertFalse(rows[0]["reason"].startswith(colours.TUPLE_REASON))
        # The grey is never an accent target: the teal accent still maps to violet.
        self.assertEqual(colours.mapping_table(self.table)["#26A69A"], "#A472F5")
        self.assertNotIn(FILAMENT_GREY, colours.mapping_table(self.table).values())

    def test_wiki_table_is_current(self) -> None:
        wiki = (REPO_ROOT / "wiki" / "cosmyx" / "branding.md").read_text(encoding="utf-8")
        self.assertIn(colours.wiki_table(self.table), wiki)

    def test_bitmap_cache_dark_snippet(self) -> None:
        snippet = self.table["snippets"][0]
        self.assertEqual(snippet["file"], "src/slic3r/GUI/BitmapCache.cpp")
        self.assertEqual(snippet["anchor"], '        replaces["#262E30"] = "#EFEFF0"; // ORCA')
        self.assertEqual(snippet["insert"], '        replaces["#8000FF"] = "#A472F5"; // Cosmyx: CSS-form brand violet on dark')
        # std::map applies quoted keys ('"' sorts before '#') first: the bare
        # key only reaches the CSS-form fills the quoted dark key misses.
        self.assertLess('"#8000FF"', "#8000FF")


# Accent usages of #26A69A, which stay violet (not filament grey).
ACCENT_FILES = (
    "src/slic3r/GUI/Widgets/HyperLink.cpp",
    "src/slic3r/GUI/Widgets/StateColor.cpp",
    "src/slic3r/GUI/ImGuiWrapper.cpp",
)


class RealTreeColoursTest(unittest.TestCase):
    """The committed colour tables on a scratch copy of this repository."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        copy_real_tree(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_release_build_accepts_the_colour_table(self) -> None:
        ctx = apply_module.Context(self.root, RELEASE)
        findings = colours.guards(ctx, "pre")
        self.assertEqual([f for f in findings if f.level == "error"], [])
        self.assertFalse([f for f in findings if "colour mapping" in f.message])

    def test_apply_leaves_no_teal_and_reverts(self) -> None:
        before = snapshot(self.root)
        lines = []
        code = apply_module.apply(self.root, env=REAL_TREE_ENV, out=lines.append)
        self.assertEqual(code, 0, "\n".join(lines))
        self.assertFalse([line for line in lines if line.startswith("error")])
        ctx = apply_module.Context(self.root, {})
        table = colours.mapping_table(ctx.colours)
        family, ignore = ctx.family()
        permits = {(row["file"], row["match"].upper()) for row in ctx.colours["allow_residue"]}
        for relative in colours.scope_paths(ctx):
            text = colours.read_scope_text(self.root, relative)
            for colour in find_hexes(text):
                self.assertNotIn(colour, table, relative)
                if in_family(colour, family, ignore):
                    self.assertIn((relative, colour), permits)
        bitmap = colours.read_scope_text(self.root, "src/slic3r/GUI/BitmapCache.cpp")
        self.assertIn('replaces["#8000FF"] = "#A472F5"; // Cosmyx', bitmap)
        self.assertIn("0xFFFF0080", bitmap)
        apply_module.revert(self.root)
        self.assertEqual(snapshot(self.root), before)

    def test_default_filament_colour_is_grey_and_accents_stay_violet(self) -> None:
        before = {relative: colours.read_scope_text(self.root, relative).count(FILAMENT_GREY) for relative in (PRESET_BUNDLE, *ACCENT_FILES)}
        lines = []
        self.assertEqual(apply_module.apply(self.root, env=REAL_TREE_ENV, out=lines.append), 0, "\n".join(lines))
        bundle = colours.read_scope_text(self.root, PRESET_BUNDLE)
        self.assertEqual(bundle.count(FILAMENT_REPLACE), 2)
        self.assertNotIn("#26A69A", bundle.upper())
        for relative in ACCENT_FILES:
            text = colours.read_scope_text(self.root, relative)
            self.assertEqual(text.count(FILAMENT_GREY), before[relative], relative)
            self.assertNotIn("#26A69A", text.upper(), relative)
            self.assertIn("#A472F5", text, relative)
        apply_module.revert(self.root)
        self.assertEqual(colours.read_scope_text(self.root, PRESET_BUNDLE).count(FILAMENT_FIND), 2)

    def test_literal_rows_are_the_same_on_a_crlf_checkout(self) -> None:
        table = branding.load_json(self.root / branding.COLOURS_FILE)
        expected = colours.literal_rows(self.root, table)
        to_crlf(self.root)
        self.assertEqual(colours.literal_rows(self.root, table), expected)
        self.assertNotIn("\r", colours.read_scope_text(self.root, "src/slic3r/GUI/BitmapCache.cpp"))


if __name__ == "__main__":
    unittest.main()
