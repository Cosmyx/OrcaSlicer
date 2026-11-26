"""Tests of the product-name stage (T11e): the token rule, the C++ lexer, the
hint and guide readers, the catalogue rename (never fuzzy), the tables, the
G8 guards on a fake tree, and a real-tree apply on a scratch copy.

Ported from the CosmoSlice product-name tests (D-001..D-006) to unittest.
"""

from __future__ import annotations

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
    guards,
    read,
    snapshot,
    write,
)

from branding import product_name  # noqa: E402
from branding.product_name import catalogues, cpp, resources, tables, tokens  # noqa: E402

graft = catalogues.graft
PN = branding.PRODUCT_NAME_DIR

# The branding mode of this run (decision 0122), resolved against this
# checkout with the engine's own brand_mode, as `just brand-check` does:
# tolerant only when the tree's upstream base is not DEV (COSMYX_BRAND_MODE,
# a build pull request into cosmyx-ci/<tag>, an integration/<tag> branch).
# An engine without modes only reads the variable.
MODE_ENV = "COSMYX_BRAND_MODE"
try:
    from branding_fixture import REAL_TREE_ENV
except ImportError:
    REAL_TREE_ENV = {MODE_ENV: os.environ.get(MODE_ENV, "")}


# ---------------------------------------------------------------- tokens


class TokenTest(unittest.TestCase):
    def test_matches_product_name(self) -> None:
        for text in ["OrcaSlicer", "Orca Slicer", "Orca will", "ORCA", "\\nOrca will", "(Orca)", "restarting Orca.",
                     "Orca-PA", "Orcslicer", "Orc Slicer", "Orcaslicer", "OrcaSlicer's"]:  # fmt: skip
            with self.subTest(text=text):
                self.assertTrue(tokens.has_token(text))

    def test_ignores_other_words_and_identifiers(self) -> None:
        for text in ["orca_slicer", "orcaslicer.com", "Orcas", "TorcaSlicer", "CosmoSlice", "orca",
                     "OrcaSlicerVersion", "ORCA_CAD_GLYPH", "OrcaSlicer_192px", "_OrcaTee", "OrcaSliced"]:  # fmt: skip
            with self.subTest(text=text):
                self.assertFalse(tokens.has_token(text))

    def test_native_tokens(self) -> None:
        self.assertTrue(tokens.has_native_token("逆戟鲸切片", "zh_CN"))
        self.assertTrue(tokens.has_native_token("逆戟鯨", "zh_TW"))
        self.assertTrue(tokens.has_native_token("오르카 슬라이서", "ko"))
        self.assertFalse(tokens.has_native_token("逆戟鲸", "fr"))
        self.assertFalse(tokens.has_native_token("오르카", None))

    def test_replace_keeps_urls_files_ids_and_kept_names(self) -> None:
        kept = [
            "https://github.com/OrcaSlicer/OrcaSlicer/wiki",
            "www.OrcaSlicer.com",
            "OrcaSlicer.exe",
            "%1%/images/%2%OrcaSlicer%3%.png",
            "orca/OrcaCube_v2.3mf",
            "OrcaSlicer/build",
            "OrcaSlicer\\\\build",
            "com.orcaslicer.OrcaSlicer",
            " Orca.Slicer.1",
            "  // ORCA: Apply bias",
            "Orca Cube",
            "Orca YOLO Flow Calibration",
            "OrcaSliced Combo",
        ]
        for text in kept:
            with self.subTest(text=text):
                self.assertEqual(tokens.replace_tokens(text), text)
                self.assertFalse(tokens.visible_name(text))

    def test_replace_prose(self) -> None:
        cases = {
            "About OrcaSlicer": "About CosmoSlice",
            "Orca Slicer will be set up": "CosmoSlice will be set up",
            "\\nOrca will cap": "\\nCosmoSlice will cap",
            "Restart Orca.": "Restart CosmoSlice.",
            "using OrcaSlicer.\\n": "using CosmoSlice.\\n",
            "Orca Cloud and OrcaSlicer": "Cosmyx Cloud and CosmoSlice",
            "Unlike OrcaSlicer, see https://orcaslicer.com/OrcaSlicer": "Unlike CosmoSlice, see https://orcaslicer.com/OrcaSlicer",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(tokens.replace_tokens(text), expected)
                self.assertTrue(tokens.visible_name(text))

    def test_replace_native_spellings(self) -> None:
        self.assertEqual(tokens.replace_tokens("오르카슬라이서가 지원", "ko"), "CosmoSlice가 지원")
        self.assertEqual(tokens.replace_tokens("오르카 슬라이서 시작", "ko"), "CosmoSlice 시작")
        self.assertEqual(tokens.replace_tokens("欢迎使用逆戟鲸", "zh_CN"), "欢迎使用CosmoSlice")
        self.assertEqual(tokens.replace_tokens("欢迎使用逆戟鲸", "fr"), "欢迎使用逆戟鲸")


CLOUD_ROWS = tokens.inflection_map(
    [
        {"language": "hu", "old": "az Orca Cloud", "new": "a Cosmyx Cloud"},
        {"language": "hu", "old": "az OrcaCloud", "new": "a Cosmyx Cloud"},
        {"language": "hu", "old": "az Orca", "new": "a CosmoSlice"},
        {"language": "ca", "old": "d'OrcaCloud", "new": "de Cosmyx Cloud"},
        {"language": "fr", "old": "d\u2019Orca Cloud", "new": "de Cosmyx Cloud"},
    ]
)


class CloudTokenTest(unittest.TestCase):
    """The upstream cloud service is renamed Cosmyx Cloud."""

    def test_renames_every_spelling(self) -> None:
        cases = {
            "Sync with Orca Cloud": "Sync with Cosmyx Cloud",
            "Export to OrcaCloud": "Export to Cosmyx Cloud",
            "Find on OrcaCloud.": "Find on Cosmyx Cloud.",
            "Sign in to Orca cloud": "Sign in to Cosmyx Cloud",
            "View on OrcaCloud <a>here</a>": "View on Cosmyx Cloud <a>here</a>",
            "Orca Cloud and OrcaSlicer": "Cosmyx Cloud and CosmoSlice",
            "Tip\\nOrcaCloud": "Tip\\nCosmyx Cloud",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(tokens.replace_tokens(text), expected)
                self.assertTrue(tokens.visible_name(text))

    def test_identifiers_urls_and_files_stay(self) -> None:
        for text in ("OrcaCloudServiceAgent", "orca_cloud", "orcacloud", "https://example.org/OrcaCloud",
                     "OrcaCloud.json", "OrcaCloudAPIError", "Cosmyx Cloud"):  # fmt: skip
            with self.subTest(text=text):
                self.assertEqual(tokens.replace_tokens(text, "hu", inflections={}), text)
                self.assertFalse(tokens.visible_name(text, "hu", {}))

    def test_glued_suffix_is_kept(self) -> None:
        # The new name ends with the same word, so a case suffix still fits.
        cases = {
            ("Orca Cloudba", "hu"): "Cosmyx Cloudba",
            ("OrcaCloudban.", "hu"): "Cosmyx Cloudban.",
            ("OrcaClouden", "eu"): "Cosmyx Clouden",
            ("Orca Cloud-ekin", "eu"): "Cosmyx Cloud-ekin",
            ("Orca Cloud'a", "tr"): "Cosmyx Cloud'a",
            ("OrcaCloud\uc5d0", "ko"): "Cosmyx Cloud\uc5d0",
            ("OrcaCloud-Plugins", "de"): "Cosmyx Cloud-Plugins",
        }
        for (text, lang), expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(tokens.replace_tokens(text, lang, inflections={}), expected)
                self.assertEqual(tokens.unresolved(text, lang, {}), [])

    def test_misspellings_in_translations(self) -> None:
        self.assertEqual(tokens.replace_tokens("OrcaSloud?", "ru", inflections={}), "Cosmyx Cloud?")
        self.assertEqual(tokens.replace_tokens("orca Cloud profilini", "tr", inflections={}), "Cosmyx Cloud profilini")

    def test_elided_or_article_lead_needs_a_row(self) -> None:
        for text, lang, form in (
            ("d'Orca Cloud", "ca", "d'Orca Cloud"),
            ("perfils d'OrcaCloud?", "ca", "d'OrcaCloud"),
            ("d\u2019Orca Cloud.", "fr", "d\u2019Orca Cloud"),
            ("az Orca Cloudba", "hu", "az Orca Cloud"),
            ("Az OrcaCloud nem", "hu", "Az OrcaCloud"),
        ):
            with self.subTest(text=text):
                self.assertEqual(tokens.unresolved(text, lang, {}), [form])
                self.assertEqual(tokens.replace_tokens(text, lang, inflections={}), text)
                self.assertTrue(tokens.visible_name(text, lang, {}))
        # "az" is a Hungarian article only.
        self.assertEqual(tokens.replace_tokens("az Orca Cloud", "de", inflections={}), "az Cosmyx Cloud")

    def test_cloud_rows_rename_before_product_rows(self) -> None:
        cases = {
            ("az Orca Cloudba, az Orca minden", "hu"): "a Cosmyx Cloudba, a CosmoSlice minden",
            ("az OrcaCloudot", "hu"): "a Cosmyx Cloudot",
            ("perfils d'OrcaCloud?", "ca"): "perfils de Cosmyx Cloud?",
            ("d\u2019Orca Cloud.", "fr"): "de Cosmyx Cloud.",
        }
        for (text, lang), expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(tokens.replace_tokens(text, lang, inflections=CLOUD_ROWS), expected)
                self.assertEqual(tokens.unresolved(text, lang, CLOUD_ROWS), [])
        text, fired = tokens.apply_inflections("az OrcaCloudot", "hu", CLOUD_ROWS)
        self.assertEqual((text, fired), ("a Cosmyx Cloudot", {"az OrcaCloud"}))


# ---------------------------------------------------------------- lexer


def raws(source: str) -> list[str]:
    return [literal.raw for literal in cpp.literals(source)]


class LexerTest(unittest.TestCase):
    def test_skips_comments_and_chars(self) -> None:
        source = """
        // "OrcaSlicer in a line comment"
        /* "OrcaSlicer in a block
           comment" */
        char c = '"'; char d = '\\'';
        auto s = "real";
        """
        self.assertEqual(raws(source), ["real"])

    def test_digit_separator_is_not_a_char_literal(self) -> None:
        self.assertEqual(raws("int n = 1'000'000; auto s = \"x\";"), ["x"])

    def test_escaped_quote_and_prefixes(self) -> None:
        found = cpp.literals('a = L"wide \\"q\\""; b = u8"utf"; c = foo"bar";')
        self.assertEqual([(lit.prefix, lit.raw) for lit in found], [("L", 'wide \\"q\\"'), ("u8", "utf"), ("", "bar")])

    def test_raw_string(self) -> None:
        found = cpp.literals('auto r = R"js(var x = "Orca"; )js"; auto t = "after"; auto u = LR"(w)";')
        self.assertEqual([lit.raw for lit in found], ['var x = "Orca"; ', "after", "w"])
        self.assertEqual([lit.prefix for lit in found], ["R", "", "LR"])
        self.assertEqual(found[0].value, 'var x = "Orca"; ')

    def test_lines_and_context(self) -> None:
        source = 'int a;\nBOOST_LOG_TRIVIAL(info) << "Orca log";\nshow(_L("Orca text"));\n#include "OrcaSlicer.hpp"\n'
        found = cpp.literals(source, "f.cpp")
        self.assertEqual([(lit.line, lit.is_log, lit.is_include) for lit in found], [(2, True, False), (3, False, False), (4, False, True)])

    def test_log_context_spans_lines(self) -> None:
        source = 'BOOST_LOG_TRIVIAL(info) << "a"\n    << "Orca b";\nshow("Orca c");'
        self.assertEqual([lit.is_log for lit in cpp.literals(source)], [True, True, False])

    def test_lines_after_block_comment_and_raw_string(self) -> None:
        source = '/* a\nb */ R"(x\ny)" "z";\n"w";'
        self.assertEqual([lit.line for lit in cpp.literals(source)], [2, 3, 4])

    def test_decode_escapes(self) -> None:
        self.assertEqual(cpp.decode('a\\nb\\t\\"q\\"\\\\'), 'a\nb\t"q"\\')
        self.assertEqual(cpp.decode("\\101\\x42\\u00e9\\013"), "ABé\x0b")
        self.assertEqual(cpp.decode("\\%"), "%")

    def test_encode_round_trip(self) -> None:
        value = 'line\n"quoted" \\ tab\tend é'
        self.assertEqual(cpp.decode(cpp.encode(value)), value)

    def test_groups_join_adjacent_literals(self) -> None:
        source = 'f(_L("Orca "\n   /* c */ "Slicer" // d\n  "!"), "other");'
        self.assertEqual([group.value for group in cpp.groups(source)], ["Orca Slicer!", "other"])

    def test_rename_keeps_the_layout_when_it_can(self) -> None:
        source = 'show(_L("Orca will "\n        "cap it"));\n'
        renamed, counts = cpp.rename(source, {"Orca will cap it": "CosmoSlice will cap it"})
        self.assertEqual(renamed, 'show(_L("CosmoSlice will "\n        "cap it"));\n')
        self.assertEqual(counts, {"Orca will cap it": 1})

    def test_rename_falls_back_to_one_literal(self) -> None:
        source = 'show(_L("Orca "\n   "Slicer is great"));\n'
        renamed, _ = cpp.rename(source, {"Orca Slicer is great": "CosmoSlice is great"})
        self.assertEqual(renamed, 'show(_L("CosmoSlice is great"));\n')
        renamed, _ = cpp.rename('auto w = L"The Orca Slicer\\n";', {"The Orca Slicer\n": 'A "new" CosmoSlice\n'})
        self.assertEqual(renamed, 'auto w = L"A \\"new\\" CosmoSlice\\n";')

    def test_rename_raw_string(self) -> None:
        source = 'doc(R"pbdoc(Loaded by OrcaSlicer.\nDone)pbdoc");'
        renamed, counts = cpp.rename(source, {"Loaded by OrcaSlicer.\nDone": "Loaded by CosmoSlice.\nDone"})
        self.assertEqual(renamed, 'doc(R"pbdoc(Loaded by CosmoSlice.\nDone)pbdoc");')
        self.assertEqual(counts, {"Loaded by OrcaSlicer.\nDone": 1})

    def test_rename_only_whole_values(self) -> None:
        source = 'a("About OrcaSlicer"); b("About OrcaSlicer today"); c("About OrcaSlicer");'
        renamed, counts = cpp.rename(source, {"About OrcaSlicer": "About CosmoSlice"})
        self.assertEqual(renamed, 'a("About CosmoSlice"); b("About OrcaSlicer today"); c("About CosmoSlice");')
        self.assertEqual(counts, {"About OrcaSlicer": 2})


# ---------------------------------------------------------------- resources


class ResourcesTest(unittest.TestCase):
    def test_hint_decode_and_rename(self) -> None:
        text = '# OrcaSlicer comment\n[hint:A]\ntext = Title\\nSay \\"OrcaSlicer\\"\n\n[hint:B]\nimage = x.png\ntext = Other\n'
        self.assertEqual(resources.decode_hint('Title\\nSay \\"x\\"'), 'Title\nSay "x"')
        renamed, counts = resources.rename_hints(text, {'Title\nSay "OrcaSlicer"': 'Title\nSay "CosmoSlice"'})
        self.assertEqual(renamed, text.replace('\\"OrcaSlicer\\"', '\\"CosmoSlice\\"'))
        self.assertEqual(counts, {'Title\nSay "OrcaSlicer"': 1})
        renamed, _ = resources.rename_hints(text, {'Title\nSay "OrcaSlicer"': "New\nline"})
        self.assertIn("text = New\\nline\n", renamed)

    def test_hint_texts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(root, resources.HINTS_FILE, '[hint:A]\ntext = Title\\nSay \\"Orca\\"\n\n[hint:B]\nimage = x.png\n')
            self.assertEqual(resources.hint_texts(root), {"hint:A": 'Title\nSay "Orca"'})

    def test_guide_texts_only_translated_elements(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write(
                root,
                f"{resources.GUIDE_DIR}/1/index.html",
                '<div data-i18n="welcome">Welcome to <b>Orca</b><br>Slicer</div>\n'
                '<div class="a trans">Orca  Slicer\n  is here</div>\n'
                '<div class="other">Orca hidden</div>\n<!-- Orca comment -->\n',
            )
            self.assertEqual(
                [text for _, _, text in resources.guide_texts(root)], ["Welcome to", "Orca", "Slicer", "Orca Slicer is here"]
            )


# ---------------------------------------------------------------- catalogues

PO = '''msgid ""
msgstr ""
"Language: ko\\n"
"Plural-Forms: nplurals=1; plural=0;\\n"

#: src/a.cpp:1
msgid "About OrcaSlicer"
msgstr "오르카 슬라이서 정보"

#, fuzzy
msgid "Restart Orca"
msgstr "오르카 재시작"

msgctxt "Menu"
msgid "Quit OrcaSlicer"
msgstr "OrcaSlicer 종료, https://github.com/OrcaSlicer/OrcaSlicer 참조"

msgid "%d Orca object"
msgid_plural "%d Orca objects"
msgstr[0] "%d 오르카 개체"

msgid "Untouched OrcaSlicer"
msgstr  "그대로  OrcaSlicer"

#~ msgid "About OrcaSlicer"
#~ msgstr "obsolete"
'''
MAPPING = {
    "About OrcaSlicer": "About CosmoSlice",
    "Restart Orca": "Restart CosmoSlice",
    "Quit OrcaSlicer": "Quit CosmoSlice",
    "%d Orca object": "%d CosmoSlice object",
    "%d Orca objects": "%d CosmoSlice objects",
}


class CatalogueTest(unittest.TestCase):
    def rename(self, text: str = PO, lang: str | None = "ko"):
        catalogue = graft.parse_po(text)
        changed = catalogues.rename_catalogue(catalogue, MAPPING, lang)
        return changed, catalogue

    def entry(self, catalogue, msgid: str):
        return next(entry for entry in catalogue.messages() if entry.msgid == msgid)

    def test_renames_msgid_and_translation_never_fuzzy(self) -> None:
        changed, catalogue = self.rename()
        self.assertEqual(changed, 4)
        about = self.entry(catalogue, "About CosmoSlice")
        self.assertEqual(about.msgstr, "CosmoSlice 정보")
        self.assertFalse(about.fuzzy)
        self.assertEqual(about.comments, ["#: src/a.cpp:1"])
        self.assertNotIn("#| ", catalogue.render())

    def test_existing_fuzzy_flag_is_kept(self) -> None:
        _, catalogue = self.rename()
        self.assertTrue(self.entry(catalogue, "Restart CosmoSlice").fuzzy)
        self.assertEqual(catalogue.render().count("fuzzy"), PO.count("fuzzy"))

    def test_context_plural_and_urls(self) -> None:
        _, catalogue = self.rename()
        quit_entry = self.entry(catalogue, "Quit CosmoSlice")
        self.assertEqual(quit_entry.msgctxt, "Menu")
        self.assertEqual(quit_entry.msgstr, "CosmoSlice 종료, https://github.com/OrcaSlicer/OrcaSlicer 참조")
        plural = self.entry(catalogue, "%d CosmoSlice object")
        self.assertEqual(plural.msgid_plural, "%d CosmoSlice objects")
        self.assertEqual(plural.msgstr_plural, {0: "%d CosmoSlice 개체"})

    def test_untouched_entries_and_obsolete_keep_their_bytes(self) -> None:
        _, catalogue = self.rename()
        text = catalogue.render()
        self.assertIn('msgid "Untouched OrcaSlicer"\nmsgstr  "그대로  OrcaSlicer"\n', text)
        self.assertIn('#~ msgid "About OrcaSlicer"\n#~ msgstr "obsolete"\n', text)
        self.assertTrue(text.startswith('msgid ""\nmsgstr ""\n"Language: ko\\n"'))

    def test_template_keeps_empty_msgstr(self) -> None:
        pot = 'msgid ""\nmsgstr ""\n\nmsgid "About OrcaSlicer"\nmsgstr ""\n'
        changed, catalogue = self.rename(pot, None)
        self.assertEqual(changed, 1)
        self.assertEqual(catalogue.render(), 'msgid ""\nmsgstr ""\n\nmsgid "About CosmoSlice"\nmsgstr ""\n')

    def test_duplicate_new_msgid_fails(self) -> None:
        text = PO + '\nmsgid "About CosmoSlice"\nmsgstr ""\n'
        with self.assertRaises(branding.BrandingError):
            self.rename(text)

    def test_cloud_name_in_translations(self) -> None:
        po = (
            'msgid ""\nmsgstr ""\n"Language: hu\\n"\n\n'
            'msgid "Find on OrcaCloud"\nmsgstr "Keresés az OrcaCloudban"\n\n'
            'msgid "Sign in to OrcaCloud"\nmsgstr "Jelentkezz be az Orca Cloudba"\n'
        )
        mapping = {"Find on OrcaCloud": "Find on Cosmyx Cloud", "Sign in to OrcaCloud": "Sign in to Cosmyx Cloud"}
        catalogue = graft.parse_po(po)
        rows = tokens.inflection_map([{"language": "hu", "old": "az OrcaCloud", "new": "a Cosmyx Cloud"}])
        self.assertEqual(catalogues.rename_catalogue(catalogue, mapping, "hu", rows), 2)
        self.assertEqual(self.entry(catalogue, "Find on Cosmyx Cloud").msgstr, "Keresés a Cosmyx Cloudban")
        # No row for the spaced spelling: left for a speaker, reported by G8.
        self.assertEqual(self.entry(catalogue, "Sign in to Cosmyx Cloud").msgstr, "Jelentkezz be az Orca Cloudba")

    def test_language_of_a_catalogue(self) -> None:
        self.assertEqual(catalogues.language("localization/i18n/fr/OrcaSlicer_fr.po"), "fr")
        self.assertIsNone(catalogues.language("localization/i18n/OrcaSlicer.pot"))


# ---------------------------------------------------------------- tables


class TablesTest(unittest.TestCase):
    ROW = {"kind": "msgid", "old": "About OrcaSlicer", "new": "About CosmoSlice", "source": "cosmyx"}

    def test_valid_rows(self) -> None:
        self.assertEqual(len(tables.rename_rows([self.ROW])), 1)
        self.assertEqual(tables.mapping([self.ROW]), {"About OrcaSlicer": "About CosmoSlice"})

    def test_rename_rejections(self) -> None:
        bad = [
            [dict(self.ROW, kind="other")],
            [dict(self.ROW, new="About OrcaSlicer")],
            [dict(self.ROW, old="About it")],
            [dict(self.ROW, new="About it")],
            [self.ROW, dict(self.ROW, new="About CosmoSlice now")],
            [self.ROW, dict(self.ROW, old="Hello OrcaSlicer")],
        ]
        for rows in bad:
            with self.subTest(rows=rows), self.assertRaises(branding.BrandingError):
                tables.rename_rows(rows)

    def test_cloud_rows(self) -> None:
        row = {"kind": "msgid", "old": "Export to OrcaCloud", "new": "Export to Cosmyx Cloud", "source": "cosmyx"}
        self.assertEqual(tables.rename_rows([row]), [row])
        for bad in (dict(row, new="Export to the cloud"), dict(row, old="Export to the cloud")):
            with self.subTest(row=bad), self.assertRaises(branding.BrandingError):
                tables.rename_rows([bad])

    def test_chain_rejected(self) -> None:
        first = {"kind": "msgid", "old": "OrcaSlicer CosmoSlice", "new": "About CosmoSlice X"}
        second = {"kind": "literal", "old": "Orca X", "new": "OrcaSlicer CosmoSlice"}
        tables.rename_rows([first])
        with self.assertRaises(branding.BrandingError):
            tables.rename_rows([first, second])

    def test_allowlist_rejections(self) -> None:
        good = {"kind": "literal", "file": "src/a.cpp", "literal": "OrcaSlicer", "count": 1, "reason": "asset: icon"}
        self.assertEqual(len(tables.allow_rows([good])), 1)
        for row in [
            dict(good, reason="because"),
            dict(good, count=0),
            dict(good, file="/abs/a.cpp"),
            {"kind": "msgid", "reason": "credit: x"},
            {"kind": "other", "reason": "credit: x"},
        ]:
            with self.subTest(row=row), self.assertRaises(branding.BrandingError):
                tables.allow_rows([row])
        with self.assertRaises(branding.BrandingError):
            tables.allow_rows([good, good])


# ---------------------------------------------------------------- plugin on a fake tree

SOURCE = (
    '#include "OrcaSlicer.hpp"\n'
    'void f() {\n'
    '    show(_L("About OrcaSlicer"));\n'
    '    BOOST_LOG_TRIVIAL(info) << "OrcaSlicer started";\n'
    '    icon("OrcaSlicer");\n'
    '    title(" - OrcaSlicer");\n'
    '    // OrcaSlicer comment\n'
    '}\n'
)
POT = 'msgid ""\nmsgstr ""\n\nmsgid "About OrcaSlicer"\nmsgstr ""\n\nmsgid "Hint\\nOrcaSlicer helps"\nmsgstr ""\n'
FR = 'msgid ""\nmsgstr ""\n"Language: fr\\n"\n\nmsgid "About OrcaSlicer"\nmsgstr "À propos de Orca Slicer"\n\nmsgid "Hint\\nOrcaSlicer helps"\nmsgstr "Astuce\\nOrcaSlicer aide"\n'
HINTS = "[hint:Help]\ntext = Hint\\nOrcaSlicer helps\n"
RENAME = [
    {"kind": "literal", "old": " - OrcaSlicer", "new": " - CosmoSlice", "source": "cosmyx"},
    {"kind": "msgid", "old": "About OrcaSlicer", "new": "About CosmoSlice", "source": "cosmyx"},
    {"kind": "msgid", "old": "Hint\nOrcaSlicer helps", "new": "Hint\nCosmoSlice helps", "source": "cosmoslice"},
]
ALLOW = [{"kind": "literal", "file": "src/slic3r/GUI/About.cpp", "literal": "OrcaSlicer", "count": 1, "reason": "asset: icon name"}]


class ProductNameTreeCase(TreeCase):
    """A fake tree with one source, the template, a French catalogue, hints and tables."""

    def setUp(self) -> None:
        super().setUp()
        write(self.root, "src/slic3r/GUI/About.cpp", SOURCE)
        write(self.root, "localization/i18n/OrcaSlicer.pot", POT)
        write(self.root, "localization/i18n/fr/OrcaSlicer_fr.po", FR)
        write(self.root, resources.HINTS_FILE, HINTS)
        self.tables(RENAME, ALLOW)

    def tables(self, rename, allow, patches=None) -> None:
        self.write_json(f"{PN}/rename.json", {"schema": 1, "rows": rename})
        self.write_json(f"{PN}/allowlist.json", {"schema": 1, "rows": allow})
        self.write_json(f"{PN}/patches.json", {"schema": 1, "rows": patches or []})

    def g8(self, phase: str, env=None):
        ctx = self.ctx(env)
        ctx.plugins = apply_module.load_plugins()
        return [finding for finding in apply_module.guards.run(ctx, phase) if finding.guard == "G8"]

    def run_apply(self, env=None):
        lines = []
        code = apply_module.apply(self.root, env={} if env is None else env, out=lines.append)
        return code, lines


class PluginTest(ProductNameTreeCase):
    def test_plugin_is_loaded(self) -> None:
        self.assertEqual(len(apply_module.load_plugins()["product_name"]), 1)

    def test_literal_and_msgid_renamed_together(self) -> None:
        before = snapshot(self.root)
        code, lines = self.run_apply()
        self.assertEqual(code, 0, "\n".join(lines))
        source = read(self.root, "src/slic3r/GUI/About.cpp").decode()
        self.assertIn('show(_L("About CosmoSlice"));', source)
        self.assertIn('title(" - CosmoSlice");', source)
        self.assertIn('"OrcaSlicer started"', source)
        self.assertIn('icon("OrcaSlicer");', source)
        self.assertIn('#include "OrcaSlicer.hpp"', source)
        self.assertIn("// OrcaSlicer comment", source)
        self.assertIn('msgid "About CosmoSlice"', read(self.root, "localization/i18n/OrcaSlicer.pot").decode())
        french = read(self.root, "localization/i18n/fr/OrcaSlicer_fr.po").decode()
        self.assertIn('msgid "About CosmoSlice"\nmsgstr "À propos de CosmoSlice"', french)
        self.assertIn('"CosmoSlice aide"', french)
        self.assertNotIn("Orca", french)
        self.assertNotIn("fuzzy", french)
        self.assertEqual(read(self.root, resources.HINTS_FILE).decode(), HINTS.replace("OrcaSlicer", "CosmoSlice"))
        apply_module.revert(self.root)
        self.assertEqual(snapshot(self.root), before)

    def test_pre_guards_pass_on_matching_tables(self) -> None:
        self.assertEqual(self.g8("pre"), [])

    def test_stale_rename_row_fails(self) -> None:
        self.tables(RENAME + [{"kind": "msgid", "old": "Gone OrcaSlicer", "new": "Gone CosmoSlice"}], ALLOW)
        found = self.g8("pre")
        self.assertEqual([f.level for f in found], ["error", "error"])
        self.assertTrue(all("stale" in f.message for f in found))
        code, _ = self.run_apply()
        self.assertEqual(code, 1)

    def test_literal_row_naming_a_msgid_fails(self) -> None:
        rename = [dict(row, kind="literal") if row["old"] == "About OrcaSlicer" else row for row in RENAME]
        self.tables(rename, ALLOW)
        self.assertIn("make it a msgid row", " ".join(f.message for f in self.g8("pre")))

    def test_msgid_row_without_literal_fails(self) -> None:
        write(self.root, "src/slic3r/GUI/About.cpp", SOURCE.replace('_L("About OrcaSlicer")', '_L("About")'))
        self.assertIn("no C++ literal or hint", " ".join(f.message for f in self.g8("pre")))

    def test_new_msgid_already_present_fails(self) -> None:
        write(self.root, "localization/i18n/OrcaSlicer.pot", POT + '\nmsgid "About CosmoSlice"\nmsgstr ""\n')
        self.assertIn("already exists", " ".join(f.message for f in self.g8("pre")))

    def test_stale_allowlist_row_fails(self) -> None:
        self.tables(RENAME, [dict(ALLOW[0], count=2)])
        found = self.g8("pre")
        self.assertEqual([f.level for f in found], ["error"])
        self.assertIn("stale allowlist", found[0].message)
        self.tables(RENAME, ALLOW + [{"kind": "msgid", "msgid": "Gone OrcaSlicer", "reason": "credit: gone"}])
        self.assertIn("stale msgid row", " ".join(f.message for f in self.g8("pre")))

    def test_residue_warns_on_development_and_fails_release(self) -> None:
        self.tables(RENAME, [])
        code, lines = self.run_apply()
        self.assertEqual(code, 0)
        self.assertTrue(any("G8" in line and "'OrcaSlicer'" in line and line.startswith("warning") for line in lines))
        self.assertEqual([f.level for f in self.g8("post", RELEASE)], ["error"])

    def test_new_upstream_msgid_is_residue(self) -> None:
        write(self.root, "src/slic3r/GUI/New.cpp", 'auto t = _L("Restart OrcaSlicer now");\n')
        write(self.root, "localization/i18n/OrcaSlicer.pot", POT + '\nmsgid "Restart OrcaSlicer now"\nmsgstr ""\n')
        _, lines = self.run_apply()
        messages = [line for line in lines if line.startswith("warning: G8")]
        self.assertTrue(any("msgid names the upstream product" in line for line in messages))
        self.assertTrue(any("literal names the upstream product" in line for line in messages))

    def test_kept_msgid_excuses_its_literal(self) -> None:
        write(self.root, "src/slic3r/GUI/New.cpp", 'auto t = _L("Credit: built on OrcaSlicer");\n')
        write(self.root, "localization/i18n/OrcaSlicer.pot", POT + '\nmsgid "Credit: built on OrcaSlicer"\nmsgstr ""\n')
        self.tables(RENAME, ALLOW + [{"kind": "msgid", "msgid": "Credit: built on OrcaSlicer", "reason": "credit: upstream"}])
        code, lines = self.run_apply()
        self.assertEqual(code, 0, "\n".join(lines))
        self.assertEqual(self.g8("post", RELEASE), [])

    def test_guide_residue_and_allowlist(self) -> None:
        write(self.root, f"{resources.GUIDE_DIR}/1/index.html", '<div data-i18n="w">Welcome to Orca Slicer</div>\n')
        _, lines = self.run_apply()
        self.assertTrue(any("guide text names the upstream product" in line for line in lines))
        rows = ALLOW + [{"kind": "text", "file": f"{resources.GUIDE_DIR}/1/index.html", "text": "Welcome to Orca Slicer", "count": 1, "reason": "kept-name: test"}]
        self.tables(RENAME, rows)
        self.assertEqual(self.run_apply()[0], 0)
        self.assertEqual(self.g8("post", RELEASE), [])

    def test_translation_left_naming_the_product_fails(self) -> None:
        from branding import product_name

        self.assertEqual(self.run_apply()[0], 0)
        relative = "localization/i18n/fr/OrcaSlicer_fr.po"
        french = read(self.root, relative).decode()
        self.assertEqual(product_name.check_translations(self.root, tables.rename_rows(RENAME)), [])
        write(self.root, relative, french.replace("À propos de CosmoSlice", "À propos de Orca"))
        found = product_name.check_translations(self.root, tables.rename_rows(RENAME))
        self.assertEqual([(f.level, f.path) for f in found], [("error", relative)])

    def test_candidates_propose_rows_for_new_upstream_text(self) -> None:
        from branding.product_name import candidates

        self.assertEqual(candidates.propose(self.root), {"rename": [], "literals": [], "stale": []})
        write(self.root, "src/slic3r/GUI/New.cpp", 'auto t = _L("Restart OrcaSlicer now"); auto u = "Hello Orca";\n')
        write(self.root, "localization/i18n/OrcaSlicer.pot", POT.replace("About OrcaSlicer", "About it") + '\nmsgid "Restart OrcaSlicer now"\nmsgstr ""\n')
        write(self.root, "src/slic3r/GUI/About.cpp", SOURCE.replace("About OrcaSlicer", "About it"))
        found = candidates.propose(self.root)
        self.assertEqual(found["rename"], [{"kind": "msgid", "old": "Restart OrcaSlicer now", "new": "Restart CosmoSlice now", "source": "cosmyx"}])
        self.assertEqual(found["literals"], [{"file": "src/slic3r/GUI/New.cpp", "literal": "Hello Orca", "count": 1, "value": "Hello Orca"}])
        self.assertEqual(found["stale"], ["About OrcaSlicer"])

    def test_patches_run_before_the_plugin_and_keep_the_app_key(self) -> None:
        patch = {"file": "version.inc", "old": 'SLIC3R_APP_NAME "OrcaSlicer"', "new": 'SLIC3R_APP_NAME "CosmoSlice"', "count": 1, "reason": "name"}
        self.tables(RENAME, ALLOW, [patch])
        code, lines = self.run_apply()
        self.assertEqual(code, 0, "\n".join(lines))
        self.assertEqual(read(self.root, "version.inc").decode(), 'set(SLIC3R_APP_NAME "CosmoSlice")\nset(SLIC3R_APP_KEY "OrcaSlicer")\n')


class TolerantTest(ProductNameTreeCase):
    """Off DEV (tolerant mode, decision 0122) a rename row whose text the
    older tree lacks entirely is skipped with a warning; strict still fails."""

    GONE = {"kind": "msgid", "old": "Gone OrcaSlicer", "new": "Gone CosmoSlice", "source": "cosmyx"}
    GONE_INFLECTION = {"language": "fr", "old": "OrcaSlicerette", "new": "CosmoSlicette", "source": "test"}

    def tolerant_g8(self, phase: str):
        ctx = self.ctx()
        ctx.plugins = apply_module.load_plugins()
        ctx.tolerant = True
        return [finding for finding in apply_module.guards.run(ctx, phase) if finding.guard == "G8"]

    def test_absent_rows_warn_in_tolerant_mode(self) -> None:
        self.tables(RENAME + [self.GONE], ALLOW + [dict(ALLOW[0], literal="Gone OrcaSlicer")])
        found = self.tolerant_g8("pre")
        self.assertTrue(found)
        self.assertEqual({f.level for f in found}, {"warning"}, found)
        self.assertTrue(all("skipped (tolerant mode)" in f.message for f in found), found)
        self.assertTrue(any("Gone OrcaSlicer" in f.message for f in found))

    def test_absent_inflection_row_warns_in_tolerant_mode(self) -> None:
        self.write_json(product_name.INFLECTIONS_FILE, {"schema": 1, "rows": [self.GONE_INFLECTION]})
        self.assertEqual({f.level for f in self.g8("pre")}, {"error"})
        found = self.tolerant_g8("pre")
        self.assertEqual([f.level for f in found], ["warning"], found)

    def test_a_partly_present_row_still_fails(self) -> None:
        # The literal is there but the template lost its msgid: not absent.
        write(self.root, "localization/i18n/OrcaSlicer.pot", POT.replace('msgid "About OrcaSlicer"\nmsgstr ""\n\n', ""))
        found = self.tolerant_g8("pre")
        self.assertIn("error", [f.level for f in found])

    def test_strict_mode_is_unchanged(self) -> None:
        self.tables(RENAME + [self.GONE], ALLOW)
        self.assertEqual([f.level for f in self.g8("pre")], ["error", "error"])

    @unittest.skipUnless(hasattr(branding, "brand_mode"), "engine without modes (before decision 0122 tolerant mode)")
    def test_tolerant_apply_skips_and_renames_the_rest(self) -> None:
        self.tables(RENAME + [self.GONE], ALLOW)
        self.assertEqual(self.run_apply()[0], 1)
        code, lines = self.run_apply(env={MODE_ENV: "tolerant"})
        self.assertEqual(code, 0, "\n".join(lines))
        self.assertTrue(any("Gone OrcaSlicer" in line and line.startswith("warning") for line in lines), lines)
        self.assertIn('show(_L("About CosmoSlice"));', read(self.root, "src/slic3r/GUI/About.cpp").decode())
        apply_module.revert(self.root)


# ---------------------------------------------------------------- the committed tables on the real tree


class RealTreeTest(unittest.TestCase):
    """Apply the committed tables to a scratch copy of this checkout's files."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls._tmp.name)
        copy_real_tree(cls.root)
        cls.before = snapshot(cls.root)
        cls.lines = []
        cls.code = apply_module.apply(cls.root, env=REAL_TREE_ENV, out=cls.lines.append)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_applies_without_error_and_no_visible_name_is_left(self) -> None:
        self.assertEqual(self.code, 0, "\n".join(self.lines))
        if REAL_TREE_ENV[MODE_ENV].strip() == "tolerant":
            # An older tree: rows it lacks are skipped, and a text upstream
            # worded differently there is drift, a warning; nothing fails.
            self.assertEqual([line for line in self.lines if "G8" in line and not line.startswith("warning")], [])
        else:
            self.assertEqual([line for line in self.lines if "G8" in line], [])

    def test_display_name_changes_and_the_app_key_stays(self) -> None:
        version = read(self.root, "version.inc").decode()
        self.assertIn('set(SLIC3R_APP_NAME "CosmoSlice")', version)
        self.assertIn('set(SLIC3R_APP_KEY "OrcaSlicer")', version)
        self.assertIn("SLIC3R_APP_KEY \" \" SoftFever_VERSION", read(self.root, "src/libslic3r/utils.cpp").decode())
        self.assertIn("{ EProducer::OrcaSlicer, SLIC3R_APP_KEY },", read(self.root, "src/libslic3r/GCode/GCodeProcessor.cpp").decode())
        self.assertIn('set (CPACK_NSIS_DISPLAY_NAME "CosmoSlice")', read(self.root, "CMakeLists.txt").decode())
        self.assertIn('set (CPACK_PACKAGE_INSTALL_REGISTRY_KEY "OrcaSlicer")', read(self.root, "CMakeLists.txt").decode())

    def test_shortcuts_run_the_renamed_executable(self) -> None:
        cmake = read(self.root, "CMakeLists.txt").decode()
        self.assertIn('set(CPACK_PACKAGE_EXECUTABLES "CosmoSlice;CosmoSlice")', cmake)
        self.assertIn('set(CPACK_CREATE_DESKTOP_LINKS "CosmoSlice")', cmake)
        self.assertIn('set (CPACK_PACKAGE_FILE_NAME "CosmoSlice_Windows_Installer_V${SoftFever_VERSION}")', cmake)
        self.assertNotIn("orca-slicer", cmake.split("set (CPACK_PACKAGE_NAME", 1)[1])

    def test_every_windows_executable_consumer_agrees(self) -> None:
        # Decision 0210: the Windows executable is CosmoSlice.exe, and every
        # place that names it (build, version resource, installer, MSIX,
        # runtime lookups) says the same name.
        import re

        def text(relative):
            return read(self.root, relative).decode("utf-8").replace("\r\n", "\n")

        gui = re.search(r'set_target_properties\(OrcaSlicer_app_gui PROPERTIES\s+OUTPUT_NAME "([^"]+)"', text("src/CMakeLists.txt"))
        exe = gui.group(1) + ".exe"
        self.assertEqual(exe, "CosmoSlice.exe")
        cmake = text("CMakeLists.txt")
        found = {
            "rc OriginalFilename": re.search(r'"OriginalFilename", "([^"]+)"', text("src/dev-utils/platform/msw/OrcaSlicer.rc.in")).group(1),
            "NSIS icon": re.search(r'CPACK_NSIS_INSTALLED_ICON_NAME "([^"]+)"', cmake).group(1),
            "Start menu": re.search(r'CPACK_PACKAGE_EXECUTABLES "([^";]+);', cmake).group(1) + ".exe",
            "desktop link": re.search(r'CPACK_CREATE_DESKTOP_LINKS "([^"]+)"', cmake).group(1) + ".exe",
            "MSIX Executable": re.search(r'Executable="([^"]+)"', text("scripts/msix/AppxManifest.xml")).group(1),
            "MSIX build check": re.search(r"Join-Path \$InstallDir '([^']+\.exe)'", text("scripts/msix/build_msix.ps1")).group(1),
        }
        plugin = text("src/slic3r/Utils/BBLNetworkPlugin.cpp")
        lookup = re.search(r'file_name_string\.find\("([^"]+)"\);\n\s*if \(found == \(file_name_string\.size\(\) - (\d+)\)\)', plugin)
        found["network plugin"] = lookup.group(1)
        for where, name in found.items():
            with self.subTest(where=where):
                self.assertEqual(name, exe)
        # The magic length is the name plus one, as upstream wrote it for orca-slicer.exe.
        self.assertEqual(int(lookup.group(2)), len(exe) + 1)
        self.assertIn(f"replace(found, {len(exe) + 1}, lib_path)", plugin)
        self.assertIn('Alias="cosmoslice.exe"', text("scripts/msix/AppxManifest.xml"))
        process = text("src/slic3r/Utils/Process.cpp")
        self.assertNotIn('"orca-slicer.exe"', process)
        self.assertIn("wxFileName(wxStandardPaths::Get().GetExecutablePath()).GetFullName()", process)
        # The Linux binary stays.
        self.assertIn('set_target_properties(OrcaSlicer PROPERTIES OUTPUT_NAME "orca-slicer")', text("src/CMakeLists.txt"))

    def test_appimage_launcher_and_its_file_agree(self) -> None:
        # LF whatever the checkout: a Windows runner (core.autocrlf) has it CRLF on disk.
        script = branding.read_lf(self.root.joinpath("src", "dev-utils", "platform", "unix", "build_appimage.sh.in"))
        self.assertIn("\nName=CosmoSlice\n", script)
        self.assertIn("mv CosmoSlice-$(uname -m).AppImage ${APP_IMAGE}", script)
        self.assertEqual(guards.appimage_pair(self.root), ("CosmoSlice", "CosmoSlice"))

    def test_flatpak_texts_name_the_product_and_keep_the_id(self) -> None:
        text = read(self.root, "scripts/flatpak/com.orcaslicer.OrcaSlicer.metainfo.xml").decode()
        self.assertIn("<id>com.orcaslicer.OrcaSlicer</id>", text)
        self.assertIn("<name>CosmoSlice</name>", text)
        description = text.split("<description>", 1)[1].split("</description>", 1)[0]
        self.assertIn("CosmoSlice is a powerful", description)
        self.assertIn("CosmoSlice also provides", description)
        self.assertNotIn("OrcaSlicer", description)
        self.assertNotIn("Orca Slicer", description)

    def test_packaging_names_stay(self) -> None:
        # Every pinned packaging identifier exists in this checkout and survives
        # the rename: the build scripts and CI find the packages by these names.
        for relative, text, _ in guards.PACKAGING_PINS:
            with self.subTest(file=relative, pin=text.strip()):
                self.assertIn(text, read(self.root, relative).decode("utf-8").replace("\r\n", "\n"))
        appimage = read(self.root, "src/dev-utils/platform/unix/build_appimage.sh.in").decode()
        self.assertNotIn("SLIC3R_APP_NAME", appimage)

    def test_upstream_tree_has_every_pin_and_a_matching_appimage_pair(self) -> None:
        for relative, text, _ in guards.PACKAGING_PINS:
            with self.subTest(file=relative):
                self.assertIn(text, self.before[relative].decode("utf-8").replace("\r\n", "\n"))

    def test_catalogues_never_get_fuzzy(self) -> None:
        for relative in catalogues.catalogue_files(self.root):
            with self.subTest(relative=relative):
                before = self.before[relative].decode("utf-8")
                after = read(self.root, relative).decode("utf-8")
                self.assertEqual(after.count("fuzzy"), before.count("fuzzy"))
                self.assertEqual(after.count("#| msgid"), before.count("#| msgid"))

    def test_zz_revert_restores_every_byte(self) -> None:
        apply_module.revert(self.root)
        self.assertEqual(snapshot(self.root), self.before)


class CrlfTest(unittest.TestCase):
    """A Windows checkout (core.autocrlf) has CRLF files: the stage reads LF
    text and writes each file back in its own line ending."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_sources_read_as_lf_and_write_back_crlf(self) -> None:
        source = 'auto a = R"(Welcome to OrcaSlicer.\n\nEnjoy)";\nauto b = "OrcaSlicer"\n    " rocks";\n'
        write(self.root, "src/a.cpp", source.replace("\n", "\r\n"))
        text = product_name.read_source(self.root, "src/a.cpp")
        self.assertEqual(text, source)
        self.assertEqual([group.value for group in cpp.groups(text, "src/a.cpp")], ["Welcome to OrcaSlicer.\n\nEnjoy", "OrcaSlicer rocks"])
        product_name.write_like(self.root, "src/a.cpp", text.replace("OrcaSlicer", "CosmoSlice"))
        self.assertEqual(read(self.root, "src/a.cpp"), source.replace("OrcaSlicer", "CosmoSlice").replace("\n", "\r\n").encode())

    def test_lf_file_stays_lf(self) -> None:
        write(self.root, "src/a.cpp", 'auto b = "OrcaSlicer";\n')
        product_name.write_like(self.root, "src/a.cpp", 'auto b = "CosmoSlice";\n')
        self.assertEqual(read(self.root, "src/a.cpp"), b'auto b = "CosmoSlice";\n')

    def test_hints_read_the_same_in_crlf(self) -> None:
        hints = "[hint:Welcome]\ntext = Welcome to OrcaSlicer\n"
        write(self.root, resources.HINTS_FILE, hints)
        expected = resources.hint_texts(self.root)
        write(self.root, resources.HINTS_FILE, hints.replace("\n", "\r\n"))
        self.assertEqual(resources.hint_texts(self.root), expected)


# ---------------------------------------------------------------- inflections and token edge cases

CS = (
    'msgid ""\nmsgstr ""\n"Language: cs\\n"\n\n'
    'msgid "About OrcaSlicer"\nmsgstr "O OrcaSliceru"\n\n'
    'msgid "Hint\\nOrcaSlicer helps"\nmsgstr "Tip\\nOrcaSlicer pomaha"\n'
)
CS_ROW = {"language": "cs", "old": "OrcaSliceru", "new": "CosmoSlicu", "source": "test"}


class InflectionTokenTest(unittest.TestCase):
    ROWS = tokens.inflection_map([CS_ROW, {"language": "hu", "old": "az OrcaSlicerrel", "new": "a CosmoSlice-szal"}])

    def test_inflected_name_is_seen_only_in_a_translation(self) -> None:
        self.assertTrue(tokens.visible_name("verze OrcaSliceru", "cs", {}))
        self.assertEqual(tokens.unresolved("verze OrcaSliceru", "cs", {}), ["OrcaSliceru"])
        self.assertFalse(tokens.visible_name("Orcas swim", None, {}))
        self.assertFalse(tokens.has_token("OrcaSliceru"))
        self.assertTrue(tokens.is_inflected("OrcaSliceru"))
        self.assertFalse(tokens.is_inflected("OrcaSlicer"))

    def test_row_renames_the_exact_form_of_its_language_only(self) -> None:
        self.assertEqual(tokens.replace_tokens("verze OrcaSliceru a OrcaSlicer", "cs", inflections=self.ROWS), "verze CosmoSlicu a CosmoSlice")
        self.assertEqual(tokens.replace_tokens("verze OrcaSliceru", "sk", inflections=self.ROWS), "verze OrcaSliceru")
        self.assertEqual(tokens.replace_tokens("az OrcaSlicerrel", "hu", inflections=self.ROWS), "a CosmoSlice-szal")
        self.assertEqual(tokens.unresolved("verze OrcaSliceru", "cs", self.ROWS), [])

    def test_row_never_touches_a_url(self) -> None:
        text = "https://example.org/OrcaSliceru"
        self.assertEqual(tokens.replace_tokens(text, "cs", inflections=self.ROWS), text)

    def test_korean_particle_is_not_an_inflection(self) -> None:
        self.assertEqual(tokens.replace_tokens("OrcaSlicer\ub294", "ko", inflections={}), "CosmoSlice\ub294")

    def test_identifiers_and_kept_names_stay(self) -> None:
        for text in ("OrcaSlicerVersion", "OrcaCloudServiceAgent", "OrcaSliced"):
            with self.subTest(text=text):
                self.assertFalse(tokens.visible_name(text, "hu", {}))

    def test_uppercase_and_combining_marks(self) -> None:
        self.assertEqual(tokens.replace_tokens("ORCASLICER ORCA SLICER ORCA"), "CosmoSlice CosmoSlice CosmoSlice")
        self.assertFalse(tokens.visible_name("OrcaSlicer\u0301"))
        self.assertTrue(tokens.visible_name("Orca\u0301 OrcaSlicer"))
        self.assertEqual(tokens.replace_tokens("Orca\u0301 OrcaSlicer"), "Orca\u0301 CosmoSlice")

    def test_app_key_names_stay_and_escapes_still_rename(self) -> None:
        self.assertEqual(tokens.replace_tokens("Open OrcaSlicer.conf"), "Open OrcaSlicer.conf")
        self.assertEqual(tokens.replace_tokens("Roaming\\\\OrcaSlicer"), "Roaming\\\\OrcaSlicer")
        self.assertEqual(tokens.replace_tokens("Hi\\nOrcaSlicer"), "Hi\\nCosmoSlice")
        self.assertEqual(tokens.replace_tokens("OrcaSlicer.\nApply"), "CosmoSlice.\nApply")


HU_PHRASES = tokens.inflection_map(
    [
        {"language": "hu", "old": "az OrcaSlicer", "new": "a CosmoSlice"},
        {"language": "hu", "old": "Az OrcaSlicer", "new": "A CosmoSlice"},
        {"language": "hu", "old": "az OrcaSlicerrel", "new": "a CosmoSlice-szal"},
        {"language": "hu", "old": "az Orca", "new": "a CosmoSlice"},
        {"language": "eu", "old": "Orca-ren", "new": "CosmoSlice-en"},
        {"language": "eu", "old": "OrcaSlicer-etik", "new": "CosmoSlice-tik"},
    ]
)


class PhraseRowTest(unittest.TestCase):
    """A row's `old` may be a phrase around the plain or hyphenated name."""

    def rename(self, text: str, lang: str) -> str:
        return tokens.replace_tokens(text, lang, inflections=HU_PHRASES)

    def test_article_phrase_is_renamed_longest_first(self) -> None:
        self.assertEqual(self.rename("az OrcaSlicerrel és az OrcaSlicer", "hu"), "a CosmoSlice-szal és a CosmoSlice")
        self.assertEqual(self.rename("Az OrcaSlicer fut.", "hu"), "A CosmoSlice fut.")
        self.assertEqual(self.rename("Tip\\nAz OrcaSlicer fut", "hu"), "Tip\\nA CosmoSlice fut")

    def test_phrase_matches_whole_words_only(self) -> None:
        self.assertEqual(self.rename("haz OrcaSlicer", "hu"), "haz CosmoSlice")
        # A longer inflected form without its row is never cut by the phrase.
        self.assertEqual(self.rename("az OrcaSlicerből", "hu"), "az OrcaSlicerből")
        self.assertEqual(tokens.unresolved("az OrcaSlicerből", "hu", HU_PHRASES), ["OrcaSlicerből"])

    def test_phrase_never_cuts_a_name_or_a_kept_name(self) -> None:
        self.assertEqual(self.rename("az Orca Slicer", "hu"), "az CosmoSlice")  # "Orca Slicer" is one name
        # The cloud name is never cut by a product row; without its own row
        # the article is left for a speaker to fix.
        self.assertEqual(self.rename("az Orca Cloud", "hu"), "az Orca Cloud")
        self.assertEqual(self.rename("az Orca minden", "hu"), "a CosmoSlice minden")

    def test_phrase_applies_in_its_language_only(self) -> None:
        self.assertEqual(self.rename("az OrcaSlicer", "de"), "az CosmoSlice")
        self.assertEqual(self.rename("Orca-ren", "hu"), "CosmoSlice-ren")

    def test_hyphenated_rows(self) -> None:
        self.assertEqual(self.rename("Orca-ren bertsioa", "eu"), "CosmoSlice-en bertsioa")
        self.assertEqual(self.rename("OrcaSlicer-etik?", "eu"), "CosmoSlice-tik?")
        self.assertEqual(self.rename("OrcaSlicer-ekin", "eu"), "CosmoSlice-ekin")  # plain rule

    def test_fired_rows(self) -> None:
        text, fired = tokens.apply_inflections("az OrcaSlicerrel", "hu", HU_PHRASES)
        self.assertEqual((text, fired), ("a CosmoSlice-szal", {"az OrcaSlicerrel"}))


class InflectionTablesTest(unittest.TestCase):
    def test_phrase_rows_are_valid(self) -> None:
        rows = [
            {"language": "hu", "old": "az OrcaSlicer", "new": "a CosmoSlice"},
            {"language": "eu", "old": "Orca-ren", "new": "CosmoSlice-en"},
            {"language": "eu", "old": "OrcaSlicer-etik", "new": "CosmoSlice-tik"},
        ]
        self.assertEqual(tables.inflection_rows(rows), rows)

    def test_rejected_phrase_rows(self) -> None:
        bad = [
            {"language": "hu", "old": "Orca Slicer", "new": "CosmoSlice"},  # bare plain name
            {"language": "hu", "old": "az Slicer", "new": "a CosmoSlice"},  # no upstream name
            {"language": "hu", "old": " az OrcaSlicer", "new": "a CosmoSlice"},  # stray space
            {"language": "hu", "old": "az OrcaSlicer", "new": "a CosmoSlice Orca"},  # new names upstream
            {"language": "hu", "old": "az OrcaSlicer", "new": "a Slice"},  # new lacks the stem
        ]
        for row in bad:
            with self.subTest(row=row), self.assertRaises(branding.BrandingError):
                tables.inflection_rows([row])

    def test_valid_row(self) -> None:
        self.assertEqual(tables.inflection_rows([CS_ROW]), [CS_ROW])

    def test_cloud_rows(self) -> None:
        rows = [
            {"language": "hu", "old": "az Orca Cloud", "new": "a Cosmyx Cloud"},
            {"language": "ca", "old": "d'OrcaCloud", "new": "de Cosmyx Cloud"},
        ]
        self.assertEqual(tables.inflection_rows(rows), rows)
        bad = [
            {"language": "ca", "old": "OrcaCloud", "new": "Cosmyx Cloud"},  # bare plain name
            {"language": "ca", "old": "d'OrcaCloud", "new": "de CosmoSlice"},  # new lacks the cloud name
            {"language": "ca", "old": "d'OrcaCloud", "new": "de Cosmyx Cloud Orca"},  # new names upstream
            {"language": "ca", "old": "d'OrcaCloud", "new": "de Orca Cloud"},  # new names the upstream cloud
        ]
        for row in bad:
            with self.subTest(row=row), self.assertRaises(branding.BrandingError):
                tables.inflection_rows([row])

    def test_rejected_rows(self) -> None:
        bad = [
            [{"language": "cs", "old": "OrcaSlicer", "new": "CosmoSlice"}],  # not inflected
            [{"language": "cs", "old": "OrcaSliceru", "new": "OrcaSlicu"}],  # new names upstream
            [{"language": "cs", "old": "OrcaSliceru", "new": "Slicu"}],  # new lacks the stem
            [{"language": "Czech", "old": "OrcaSliceru", "new": "CosmoSlicu"}],
            [{"language": "cs", "old": "OrcaSliceru"}],
            [CS_ROW, dict(CS_ROW)],
            "rows",
        ]
        for rows in bad:
            with self.subTest(rows=rows):
                with self.assertRaises(branding.BrandingError):
                    tables.inflection_rows(rows)


class InflectionPluginTest(ProductNameTreeCase):
    def setUp(self) -> None:
        super().setUp()
        write(self.root, "localization/i18n/cs/OrcaSlicer_cs.po", CS)

    def inflections(self, rows) -> None:
        self.write_json(f"{PN}/inflections.json", {"schema": 1, "rows": rows})

    def test_missing_row_is_reported_as_needs_inflection_row(self) -> None:
        code, lines = self.run_apply()
        self.assertEqual(code, 0, "\n".join(lines))
        czech = read(self.root, "localization/i18n/cs/OrcaSlicer_cs.po").decode()
        self.assertIn('msgid "About CosmoSlice"\nmsgstr "O OrcaSliceru"', czech)
        self.assertIn('"CosmoSlice pomaha"', czech)
        needs = [line for line in lines if "needs inflection row (cs): OrcaSliceru" in line]
        self.assertEqual(len(needs), 1, "\n".join(lines))
        self.assertTrue(needs[0].startswith("warning:"), needs[0])

    def test_missing_row_fails_a_release_build(self) -> None:
        self.assertEqual(self.run_apply()[0], 0)
        found = [f for f in self.g8("post", RELEASE) if "needs inflection row" in f.message]
        self.assertEqual([(f.level, f.path) for f in found], [("error", "localization/i18n/cs/OrcaSlicer_cs.po")])

    def test_row_renames_the_translation(self) -> None:
        self.inflections([CS_ROW])
        code, lines = self.run_apply()
        self.assertEqual(code, 0, "\n".join(lines))
        self.assertFalse(any("G8" in line for line in lines), "\n".join(lines))
        self.assertIn('msgstr "O CosmoSlicu"', read(self.root, "localization/i18n/cs/OrcaSlicer_cs.po").decode())

    def test_stale_row_is_an_error(self) -> None:
        self.inflections([CS_ROW, {"language": "cs", "old": "OrcaSlicerem", "new": "CosmoSlicem"}])
        found = [f for f in self.g8("pre") if "stale inflection row" in f.message]
        self.assertEqual([(f.level, "OrcaSlicerem" in f.message) for f in found], [("error", True)])

    def test_invalid_table_is_an_error(self) -> None:
        self.inflections([{"language": "cs", "old": "OrcaSlicer", "new": "CosmoSlice"}])
        self.assertTrue(any(f.level == "error" and "inflection row" in f.message for f in self.g8("pre")))

    def test_list_names_every_form_with_an_example(self) -> None:
        from branding.product_name import inflections

        listed = inflections.needed(self.root)
        self.assertEqual(list(listed), ["cs"])
        self.assertEqual(
            listed["cs"]["inflected"],
            [{"form": "OrcaSliceru", "count": 1, "example_msgid": "About OrcaSlicer", "example_translation": "O OrcaSliceru"}],
        )
        self.inflections([CS_ROW])
        self.assertEqual(inflections.needed(self.root), {})

    def test_row_shadowed_by_a_longer_row_is_stale(self) -> None:
        hu = (
            'msgid ""\nmsgstr ""\n"Language: hu\\n"\n\n'
            'msgid "About OrcaSlicer"\nmsgstr "Az OrcaSlicer-ről, az OrcaSlicerrel"\n'
        )
        write(self.root, "localization/i18n/hu/OrcaSlicer_hu.po", hu)
        self.inflections(
            [
                CS_ROW,
                {"language": "hu", "old": "az OrcaSlicerrel", "new": "a CosmoSlice-szal", "source": "test"},
                {"language": "hu", "old": "OrcaSlicerrel", "new": "CosmoSlice-szal", "source": "test"},
                {"language": "hu", "old": "Az OrcaSlicer-ről", "new": "A CosmoSlice-ról", "source": "test"},
            ]
        )
        found = [f.message for f in self.g8("pre") if "stale inflection row" in f.message]
        self.assertEqual(found, ["stale inflection row hu 'OrcaSlicerrel': no renamed translation has it"])

    def test_hyphenated_form_renamed_by_a_row_is_not_listed(self) -> None:
        from branding.product_name import inflections

        eu = 'msgid ""\nmsgstr ""\n"Language: eu\\n"\n\nmsgid "About OrcaSlicer"\nmsgstr "OrcaSlicer-etik eta OrcaSlicer-ekin"\n'
        write(self.root, "localization/i18n/eu/OrcaSlicer_eu.po", eu)
        self.inflections([CS_ROW, {"language": "eu", "old": "OrcaSlicer-etik", "new": "CosmoSlice-tik", "source": "test"}])
        listed = inflections.needed(self.root)
        self.assertEqual([item["form"] for item in listed["eu"]["hyphenated"]], ["OrcaSlicer-ekin"])
        code, lines = self.run_apply()
        self.assertEqual(code, 0, "\n".join(lines))
        self.assertIn('msgstr "CosmoSlice-tik eta CosmoSlice-ekin"', read(self.root, "localization/i18n/eu/OrcaSlicer_eu.po").decode())


class NonUtf8InputTest(ProductNameTreeCase):
    def test_non_utf8_hints_is_a_clean_finding(self) -> None:
        repo = self.root / resources.HINTS_FILE
        repo.write_bytes("[hint:Help]\ntext = Caf\u00e9 OrcaSlicer\n".encode("latin-1"))
        found = self.g8("pre")
        self.assertTrue(any(f.level == "error" and "not UTF-8" in f.message for f in found), found)
        code, lines = self.run_apply()
        self.assertNotEqual(code, 0)
        self.assertFalse(any("Traceback" in line for line in lines))


class CommittedTablesTest(unittest.TestCase):
    def test_tables_are_valid_and_canonical(self) -> None:
        for name in ("rename", "allowlist", "patches", "inflections"):
            path = REPO_ROOT / PN / f"{name}.json"
            data = branding.load_json(path)
            self.assertEqual(data["schema"], 1)
            # Line endings aside: a Windows checkout (core.autocrlf) holds it in CRLF.
            self.assertTrue(branding.same_text(path, branding.dump_json(data)), name)
        rename = tables.rename_rows(branding.load_json(REPO_ROOT / PN / "rename.json")["rows"])
        tables.allow_rows(branding.load_json(REPO_ROOT / PN / "allowlist.json")["rows"])
        rows = tables.inflection_rows(branding.load_json(REPO_ROOT / PN / "inflections.json")["rows"])
        keys = [(row["language"], row["old"]) for row in rows]
        self.assertEqual(keys, sorted(keys), "inflection rows are sorted by language, then old")
        self.assertTrue(all(row.get("source") for row in rows), "every inflection row says where it comes from")
        self.assertEqual(sum(1 for row in rename if row["source"] == "cosmoslice"), 48)

    def test_appimage_name_and_move_rows_go_together(self) -> None:
        # Decision 0210 (and 0132's history): renaming the AppImage desktop
        # Name= without its mv row breaks the Linux packaging, and the other
        # way round.
        rows = branding.load_json(REPO_ROOT / PN / "patches.json")["rows"]
        script = "src/dev-utils/platform/unix/build_appimage.sh.in"
        name = [row for row in rows if row["file"] == script and "Name=" in row["old"]]
        move = [row for row in rows if row["file"] == script and row["old"].startswith("mv ")]
        self.assertEqual(len(name), len(move))
        for row_name, row_move in zip(name, move):
            new_name = row_name["new"].strip("\n").split("=", 1)[1]
            self.assertTrue(row_move["new"].startswith(f"mv {new_name}-$(uname -m).AppImage"))

    def test_build_win_bat_is_never_patched(self) -> None:
        # Upstream's scripts/test_build_win.ps1 asserts build_win.bat's text.
        rows = branding.load_json(REPO_ROOT / PN / "patches.json")["rows"]
        self.assertEqual([row for row in rows if row["file"] == "build_win.bat"], [])

    def test_rename_keeps_texts_asserted_by_upstream_tests(self) -> None:
        # An upstream test that asserts a text the rename rewrites fails on
        # every branded build: such a text is kept (allowlisted), never renamed.
        rename = branding.load_json(REPO_ROOT / PN / "rename.json")["rows"]
        olds = [row["old"] for row in rename]
        tests_dir = REPO_ROOT / "tests"
        hits = []
        for path in sorted(tests_dir.rglob("*.cpp")):
            if branding.is_cosmyx_path(branding.relative_posix(REPO_ROOT, path)):
                continue
            text = path.read_bytes().decode("utf-8", "replace")
            if "Orc" not in text:
                continue
            hits += [(branding.relative_posix(REPO_ROOT, path), old[:60]) for old in olds if old in text]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
