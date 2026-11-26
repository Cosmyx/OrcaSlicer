"""Tests of the SVG recolour candidates (scripts/cosmyx/branding/candidates.py):
the SVG rewrite rule, generation and its G4 report, the review sheets with the
simulated BitmapCache colour maps, accept into the overlay, and a run on a
scratch copy of this repository."""

from __future__ import annotations

import base64
import copy
import json
import os
import re
import tempfile
import unittest
from pathlib import Path

from branding_fixture import (
    REPO_ROOT,
    TreeCase,
    apply_module,
    branding,
    copy_real_tree,
    manifest,
    read,
    snapshot,
    svg,
    write,
)
from branding import candidates, in_family

# The branding mode of this run (decision 0122): the cosmyx-prepare action
# exports COSMYX_BRAND_MODE, tolerant only when the tree's upstream base is not
# DEV. An older base lacks some of the icons the DEV manifest lists.
TOLERANT = os.environ.get("COSMYX_BRAND_MODE", "").strip() == "tolerant"

TABLE_MAP = {"#009688": "#8000FF", "#00675B": "#A472F5"}

TABLE = {
    "schema": 1,
    "palette": {"brand": "#8000FF", "brand_dark_screen": "#A472F5", "lavender": "#B4B9DD"},
    "mappings": [
        {"from": "#009688", "to": "#8000FF", "role": "light base", "source": "user", "status": "validated"},
        {"from": "#00675B", "to": "#A472F5", "role": "dark base", "source": "user", "status": "validated"},
        {"from": "#26A69A", "to": "#A472F5", "role": "hover", "source": "derived", "status": "to-validate"},
    ],
    "ignore": ["#00AE42", "#1F8EEA"],
    "scopes": ["src/slic3r/*.cpp", "!src/slic3r/GUI/Cosmyx/*"],
    "literals": [],
    "snippets": [
        {
            "file": "src/slic3r/GUI/BitmapCache.cpp",
            "anchor": '        replaces["#262E30"] = "#EFEFF0"; // ORCA',
            "insert": '        replaces["#8000FF"] = "#A472F5"; // Cosmyx: CSS-form brand violet on dark',
            "count": 1,
            "reason": "dark mode CSS form",
        }
    ],
    "allow_residue": [],
}

BITMAP_CACHE = """\
    // map of color replaces
    std::map<std::string, std::string> replaces;
    replaces["\\"#00FF00\\""] = "\\"#52c7b8\\"";
    if (dark_mode) {
        replaces["\\"#00FF00\\""] = "\\"#FF0000\\"";
        replaces["\\"#009688\\""] = "\\"#00675b\\"";
        //replaces["\\"#ACACAC\\""] = "\\"#54545A\\"";
        replaces["#262E30"] = "#EFEFF0"; // ORCA
    } else {
        replaces["#949494"] = "#7C8282"; // ORCA
    }

    if (strstr(bitmap_name.c_str(), "toggle_on") != NULL && dark_mode)
        replaces["#009688"] = "#00675b";
"""

APPLE = "resources/images/apple.svg"
ZEBRA = "resources/images/zebra.svg"
CHECK = "resources/web/img/check_g.svg"


def rewrite(text: str) -> str:
    return candidates.recolour_svg(text, TABLE_MAP)[0]


class RecolourSvgTest(unittest.TestCase):
    def test_attribute_style_and_style_element_become_uppercase(self) -> None:
        text = (
            '<svg><style>.a { fill: #009688; } .b{stroke:#00675b}</style>'
            '<rect fill="#009688" style="stroke:#00675b;fill:#009688"/>'
            "<stop stop-color='#009688'/></svg>"
        )
        self.assertEqual(
            rewrite(text),
            '<svg><style>.a { fill: #8000FF; } .b{stroke:#A472F5}</style>'
            '<rect fill="#8000FF" style="stroke:#A472F5;fill:#8000FF"/>'
            "<stop stop-color='#8000FF'/></svg>",
        )

    def test_counts(self) -> None:
        _, counts = candidates.recolour_svg('<a fill="#009688" stroke="#009688" color="#00675B"/>', TABLE_MAP)
        self.assertEqual(counts, {"#009688": 2, "#00675B": 1})

    def test_eight_digit_colour_keeps_its_alpha(self) -> None:
        self.assertEqual(rewrite('<a fill="#009688cc"/>'), '<a fill="#8000FFcc"/>')

    def test_id_href_url_and_base64_never_change(self) -> None:
        for text in (
            '<g id="#009688"/>',
            '<use href="#009688"/>',
            '<use xlink:href="#009688"/>',
            '<rect fill="url(#009688)"/>',
            '<a fill="https://example.invalid/x#009688"/>',
            '<text value="&#009688;"/>',
        ):
            with self.subTest(text=text):
                self.assertEqual(rewrite(text), text)

    def test_text_comments_cdata_and_selectors_never_change(self) -> None:
        for text in (
            "<text>#009688</text>",
            '<!-- <rect fill="#009688"/> -->',
            '<![CDATA[ <rect fill="#009688"/> ]]>',
            "<style>#009688 { }</style>",
            "<title>colour #00675B</title>",
        ):
            with self.subTest(text=text):
                self.assertEqual(rewrite(text), text)

    def test_unmapped_colours_and_layout_are_kept(self) -> None:
        text = '<?xml version="1.0"?>\r\n<svg>\r\n  <rect fill="#33aba1" stroke="#009688"/>\r\n</svg>'
        self.assertEqual(rewrite(text), text.replace("#009688", "#8000FF"))

    def test_teal_left(self) -> None:
        left = candidates.teal_left('<a fill="#33aba1" stroke="#808080"/>', None, ["#00AE42"])
        self.assertEqual(left, ["#33ABA1"])

    def test_only_validated_mappings_are_used(self) -> None:
        self.assertEqual(candidates.validated_table(TABLE), {"#009688": "#8000FF", "#00675B": "#A472F5"})


class ColourMapTest(unittest.TestCase):
    def test_parse_light_and_dark_maps(self) -> None:
        maps = candidates.parse_colour_maps(BITMAP_CACHE)
        self.assertEqual(maps["light"], {'"#00FF00"': '"#52c7b8"', "#949494": "#7C8282"})
        self.assertEqual(
            maps["dark"],
            {'"#00FF00"': '"#FF0000"', '"#009688"': '"#00675b"', "#262E30": "#EFEFF0"},
        )

    def test_branded_source_has_the_snippet_and_the_rewrite(self) -> None:
        maps = candidates.parse_colour_maps(candidates.branded_source(BITMAP_CACHE, TABLE))
        self.assertEqual(maps["dark"]['"#8000FF"'], '"#A472F5"')
        self.assertEqual(maps["dark"]["#8000FF"], "#A472F5")
        self.assertNotIn('"#009688"', maps["dark"])

    def test_map_order_follows_std_map(self) -> None:
        # Quoted keys sort before bare ones and are applied first.
        result = candidates.apply_map('<a fill="#8000FF" style="fill:#8000FF"/>', {'"#8000FF"': '"#A472F5"', "#8000FF": "#000000"})
        self.assertEqual(result, '<a fill="#A472F5" style="fill:#000000"/>')

    def test_missing_declaration_refuses(self) -> None:
        with self.assertRaises(branding.BrandingError):
            candidates.parse_colour_maps("int main() {}\n")


class CandidatesTreeTest(TreeCase):
    def setUp(self) -> None:
        super().setUp()
        self.table = copy.deepcopy(TABLE)
        self.write_json(branding.COLOURS_FILE, self.table)
        write(self.root, candidates.BITMAP_CACHE, BITMAP_CACHE)

    def generate(self) -> dict:
        return candidates.generate(self.root)

    def candidate(self, path: str) -> bytes:
        return read(self.root, f"{candidates.CANDIDATES_DIR}/{path}")

    def test_generate_writes_recolour_candidates_only(self) -> None:
        before = snapshot(self.root)
        index = self.generate()
        self.assertEqual(snapshot(self.root), before)
        paths = [entry["path"] for entry in index["candidates"]]
        self.assertEqual(paths, [APPLE, CHECK])
        self.assertIn(b'fill="#8000FF"', self.candidate(APPLE))
        self.assertIn(b'fill="#A472F5"', self.candidate(CHECK))
        # The logo is T11b's; #26A69A is not validated, so zebra has no candidate.
        self.assertEqual([entry["path"] for entry in index["unchanged"]], [ZEBRA])
        self.assertEqual(index["unchanged"][0]["teal_left"], ["#26A69A"])
        self.assertEqual(index["unvalidated_mappings"], ["#26A69A"])
        self.assertFalse((self.root / candidates.CANDIDATES_DIR / "resources/images/OrcaSlicer.svg").exists())

    def test_generate_reports_g4_and_skips_unlisted_teal(self) -> None:
        write(self.root, "resources/images/new_icon.svg", svg("#009688"))
        index = self.generate()
        self.assertEqual(index["unlisted"], ["resources/images/new_icon.svg"])
        self.assertNotIn("resources/images/new_icon.svg", [entry["path"] for entry in index["candidates"]])
        lines = candidates.generate_report(index)
        self.assertTrue(any(line.startswith("warning: G4 resources/images/new_icon.svg") for line in lines), lines)
        g4 = self.findings(guard="G4")
        self.assertEqual([finding.path for finding in g4], ["resources/images/new_icon.svg"])

    def test_generate_empties_stale_candidates(self) -> None:
        self.generate()
        stale = write(self.root, f"{candidates.CANDIDATES_DIR}/resources/images/old.svg", "x")
        self.generate()
        self.assertFalse(stale.exists())

    def test_generate_refuses_a_branded_tree(self) -> None:
        apply_module.State(self.root).save()
        with self.assertRaises(branding.BrandingError):
            self.generate()

    def test_review_is_self_contained(self) -> None:
        self.generate()
        written = candidates.review(self.root)
        self.assertEqual(written[0], f"{candidates.REVIEW_DIR}/index.html")
        self.assertEqual(written[1:], [f"{candidates.REVIEW_DIR}/icons-a-m.html", f"{candidates.REVIEW_DIR}/web.html"])
        sheet = read(self.root, written[1]).decode("utf-8")
        sources = re.findall(r'src="([^"]*)"', sheet)
        self.assertEqual(len(sources), 4)
        self.assertTrue(all(source.startswith("data:image/svg+xml;base64,") for source in sources))
        self.assertNotRegex(sheet, r"<(script|link|iframe|object|embed)\b")
        self.assertIn("#1C1C1F", sheet)
        self.assertIn("#FFFFFF", sheet)
        # The dark "after" cell goes through the branded dark map.
        dark_after = base64.b64decode(sources[3].split(",", 1)[1]).decode("utf-8")
        self.assertIn('fill="#A472F5"', dark_after)
        light_after = base64.b64decode(sources[1].split(",", 1)[1]).decode("utf-8")
        self.assertIn('fill="#8000FF"', light_after)

    def test_review_needs_candidates_and_bitmap_cache(self) -> None:
        with self.assertRaises(branding.BrandingError):
            candidates.review(self.root)
        self.generate()
        (self.root / candidates.BITMAP_CACHE).unlink()
        with self.assertRaises(branding.BrandingError):
            candidates.review(self.root)

    def test_accept_records_to_validate_candidate_rows(self) -> None:
        self.generate()
        self.assertEqual(candidates.accept(self.root, "icons-a-m"), [APPLE])
        overlay = manifest.overlay_path(self.root, APPLE)
        self.assertEqual(overlay.read_bytes(), self.candidate(APPLE))
        _, row = manifest.load(self.root).by_path()[APPLE]
        self.assertEqual((row["kind"], row["source"], row["status"]), ("recolour", "candidate", "to-validate"))
        self.assertEqual(row["override_sha256"], branding.file_sha256(overlay))
        self.assertTrue(row["source_ref"].startswith("just brand-candidates"))
        errors = [finding for finding in self.findings() if finding.level == "error"]
        self.assertEqual(errors, [])
        self.assertEqual(manifest.validate(self.root), [])

    def test_accept_glob_and_no_match(self) -> None:
        self.generate()
        self.assertEqual(candidates.accept(self.root, "resources/web/*"), [CHECK])
        with self.assertRaises(branding.BrandingError):
            candidates.accept(self.root, "resources/none/*")

    def test_accept_is_all_or_nothing(self) -> None:
        self.generate()
        write(self.root, f"{candidates.CANDIDATES_DIR}/{CHECK}", "edited")
        before = snapshot(self.root)
        with self.assertRaises(branding.BrandingError):
            candidates.accept(self.root, "resources/*")
        self.assertEqual(snapshot(self.root), before)

    def test_accept_refuses_stale_inputs(self) -> None:
        self.generate()
        write(self.root, APPLE, svg("#00675B"))
        with self.assertRaises(branding.BrandingError):
            candidates.accept(self.root, APPLE)
        write(self.root, APPLE, TREE_APPLE)
        self.table["mappings"][2]["status"] = "validated"
        self.write_json(branding.COLOURS_FILE, self.table)
        with self.assertRaises(branding.BrandingError):
            candidates.accept(self.root, APPLE)

    def test_accept_refuses_a_row_with_an_overlay(self) -> None:
        self.generate()
        candidates.accept(self.root, APPLE)
        with self.assertRaises(branding.BrandingError):
            candidates.accept(self.root, APPLE)

    def test_cli(self) -> None:
        lines = []
        self.assertEqual(candidates.main(["accept", "web"], root=self.root, out=lines.append), 2)
        self.assertEqual(candidates.main(["generate"], root=self.root, out=lines.append), 0)
        self.assertEqual(lines[0], "2 candidate(s) in build/cosmyx/candidates/.")
        self.assertEqual(candidates.main(["review"], root=self.root, out=lines.append), 0)
        self.assertTrue(any(line.startswith("Review sheet: ") for line in lines))


TREE_APPLE = svg("#009688")


class RealTreeCandidatesTest(unittest.TestCase):
    """The committed tables on a scratch copy of this repository."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        copy_real_tree(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_every_teal_svg_is_accepted(self) -> None:
        # The user approved every candidate: the committed tables have none left to propose.
        self.assertEqual(candidates.candidate_rows(self.root), [])
        self.assertEqual(candidates.unlisted_teal(self.root, branding.load_json(REPO_ROOT / branding.COLOURS_FILE)), [])

    def test_generate_and_review_run_clean(self) -> None:
        # Turn the accepted rows back to missing so generate runs over every real teal SVG.
        for manifest_file in sorted((self.root / "cosmyx-src/branding/manifest").glob("*.json")):
            table = json.loads(manifest_file.read_text(encoding="utf-8"))
            if table["group"] not in candidates.CANDIDATE_GROUPS:
                continue
            for row in table["rows"]:
                if row["source"] == "candidate":
                    row["status"] = "missing"
            manifest_file.write_text(json.dumps(table, indent=2) + "\n", encoding="utf-8")
        index = candidates.generate(self.root)
        rows = candidates.candidate_rows(self.root)
        if TOLERANT:
            # generate skips a row whose icon this older tree does not have.
            rows = [(group, row) for group, row in rows if (self.root / row["path"]).is_file()]
        self.assertGreater(len(index["candidates"]), 0)
        self.assertEqual(len(index["candidates"]) + len(index["unchanged"]), len(rows))
        self.assertEqual(index["unlisted"], [])
        table = branding.load_json(REPO_ROOT / branding.COLOURS_FILE)
        family, ignore = candidates.family_of(table)
        mapped_targets = set(candidates.validated_table(table).values())
        for entry in index["candidates"]:
            text = read(self.root, f"{candidates.CANDIDATES_DIR}/{entry['path']}").decode("utf-8", "replace")
            with self.subTest(path=entry["path"]):
                self.assertTrue(set(branding.find_hexes(text)) & mapped_targets)
                # Teal left only where no validated mapping exists for it.
                for colour in entry["teal_left"]:
                    self.assertTrue(in_family(colour, family, ignore))
                    self.assertNotIn(colour, candidates.validated_table(table))
        written = candidates.review(self.root)
        self.assertTrue((self.root / written[0]).is_file())
        self.assertEqual(len(written), 4)


if __name__ == "__main__":
    unittest.main()
