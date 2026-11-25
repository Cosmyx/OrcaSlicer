"""Checks of the Cosmyx UI languages (decision 0220): the table, the Cosmyx
language catalogues, their build-time install and the hooks."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

COSMYX_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = COSMYX_DIR.parents[1]
sys.path.insert(0, str(COSMYX_DIR))


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, COSMYX_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


languages = load_module("languages")
g = sys.modules["i18n_graft"]

# The user's decision, written out independently of the table.
OFFERED = [
    "ar_SA", "da_DK", "de_DE", "el_GR", "en_GB", "es_ES", "fi_FI", "fr_FR", "ga_IE", "hi_IN", "it_IT", "ja_JP",
    "ko_KR", "nb_NO", "nl_BE", "nl_NL", "pl_PL", "pt_PT", "sv_SE", "uk_UA", "vi_VN", "zh_CN", "zh_HK", "zh_TW",
]
DROPPED = ["ca", "cs", "eu", "hu", "lt", "pt_BR", "ru", "th", "tr"]

# Plural rules of the languages Cosmyx adds (CLDR integer rules).
PLURAL_FORMS = {
    "ar_SA": "nplurals=6; plural=(n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : n%100>=3 && n%100<=10 ? 3 : n%100>=11 ? 4 : 5);",
    "da_DK": "nplurals=2; plural=(n != 1);",
    "el_GR": "nplurals=2; plural=(n != 1);",
    "en_GB": "nplurals=2; plural=(n != 1);",
    "fi_FI": "nplurals=2; plural=(n != 1);",
    "ga_IE": "nplurals=5; plural=(n==1 ? 0 : n==2 ? 1 : n>=3 && n<=6 ? 2 : n>=7 && n<=10 ? 3 : 4);",
    "hi_IN": "nplurals=2; plural=(n > 1);",
    "nb_NO": "nplurals=2; plural=(n != 1);",
    "nl_BE": "nplurals=2; plural=(n != 1);",
    "pt_PT": "nplurals=2; plural=(n != 1);",
    "zh_HK": "nplurals=1; plural=0;",
}

ROWS = languages.load_table(REPO_ROOT)


def find_msgfmt() -> str | None:
    found = shutil.which("msgfmt")
    if found:
        return found
    bundled = REPO_ROOT / "tools" / "msgfmt.exe"
    return str(bundled) if os.name == "nt" and bundled.is_file() else None


class TableTests(unittest.TestCase):
    def test_exactly_the_offered_languages(self) -> None:
        self.assertEqual([row.code for row in ROWS], OFFERED)

    def test_table_keeps_its_rules(self) -> None:
        self.assertEqual(languages.table_errors(ROWS), [])

    def test_only_arabic_is_right_to_left(self) -> None:
        self.assertEqual([row.code for row in ROWS if row.rtl], ["ar_SA"])

    def test_cosmyx_rows_and_seeds(self) -> None:
        cosmyx = {row.code: row.seed for row in ROWS if row.source == "Cosmyx"}
        self.assertEqual(set(cosmyx), set(PLURAL_FORMS))
        self.assertEqual({code: seed for code, seed in cosmyx.items() if seed}, {"en_GB": "en", "nl_BE": "nl", "pt_PT": "pt_BR", "zh_HK": "zh_TW"})
        for row in ROWS:
            if row.source == "Cosmyx":
                with self.subTest(code=row.code):
                    self.assertEqual(row.plural_forms, PLURAL_FORMS[row.code])

    def test_upstream_rows_map_to_existing_catalogues(self) -> None:
        upstream = g.orca_languages(REPO_ROOT / "localization" / "i18n")
        for row in ROWS:
            if row.source == "Upstream":
                with self.subTest(code=row.code):
                    self.assertIn(row.catalog, upstream)
                    self.assertEqual(row.catalog, row.code if row.code.startswith("zh") else row.language)

    def test_dropped_upstream_languages(self) -> None:
        self.assertEqual(languages.dropped_languages(REPO_ROOT, ROWS), DROPPED)

    def test_parser_refuses_malformed_rows(self) -> None:
        good = 'COSMYX_UI_LOCALE("da_DK", DANISH, "da_DK", Cosmyx, "", "Dansk", false, Latin, "nplurals=2; plural=(n != 1);")'
        self.assertEqual(len(languages.parse_table(good)), 1)
        for bad in (
            good.replace(', Latin', ''),
            good.replace('false', '"false"'),
            good.replace('Dansk"', 'Dansk",'),
            good.replace('"Dansk"', '"Dan\\"sk"'),
            good + " extra",
            good.replace(", DANISH,", " DANISH,"),
        ):
            with self.subTest(row=bad), self.assertRaises(languages.TableError):
                languages.parse_table(bad)

    def test_rule_violations_are_reported(self) -> None:
        row = next(r for r in ROWS if r.code == "da_DK")
        broken = [
            languages.UiLocale(**{**row.__dict__, "plural_forms": ""}),
            languages.UiLocale(**{**row.__dict__, "code": "fr_FR", "catalog": "da_DK"}),
        ]
        errors = languages.table_errors(broken)
        self.assertTrue(any("plural forms" in e for e in errors), errors)
        self.assertTrue(any("another language" in e for e in errors), errors)


class CommittedCataloguesTests(unittest.TestCase):
    def test_check_passes(self) -> None:
        self.assertEqual(languages.check(REPO_ROOT, ROWS), [])

    def test_seeded_entries_are_marked_for_review(self) -> None:
        for row in ROWS:
            if row.source != "Cosmyx" or not row.seed:
                continue
            with self.subTest(code=row.code):
                catalogue = g.read_po(languages.cosmyx_catalogue(REPO_ROOT, row))
                for entry in catalogue.messages():
                    if entry.translated:
                        self.assertTrue(any(c.startswith(languages.REVIEW_PREFIX) for c in entry.comments), entry.msgid)

    def test_unseeded_catalogues_start_untranslated(self) -> None:
        for row in ROWS:
            if row.source == "Cosmyx" and not row.seed:
                with self.subTest(code=row.code):
                    catalogue = g.read_po(languages.cosmyx_catalogue(REPO_ROOT, row))
                    self.assertFalse([e.msgid for e in catalogue.messages() if e.translated])

    def test_catalogues_are_lf_utf8(self) -> None:
        for row in ROWS:
            if row.source == "Cosmyx":
                with self.subTest(code=row.code):
                    data = languages.cosmyx_catalogue(REPO_ROOT, row).read_bytes()
                    self.assertNotIn(b"\r\n", data)
                    data.decode("utf-8")

    def test_generate_is_stable(self) -> None:
        # Regenerating from the committed files must not change a byte.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(REPO_ROOT / "localization" / "cosmyx" / "i18n", root / "localization" / "cosmyx" / "i18n")
            (root / "localization" / "i18n").mkdir(parents=True)
            shutil.copyfile(REPO_ROOT / "localization" / "i18n" / "OrcaSlicer.pot", root / "localization" / "i18n" / "OrcaSlicer.pot")
            for row in ROWS:
                if row.seed:
                    target = root / "localization" / "i18n" / row.seed
                    target.mkdir(exist_ok=True)
                    shutil.copyfile(REPO_ROOT / "localization" / "i18n" / row.seed / f"OrcaSlicer_{row.seed}.po", target / f"OrcaSlicer_{row.seed}.po")
            languages.generate(root, ROWS)
            for row in ROWS:
                if row.source == "Cosmyx":
                    with self.subTest(code=row.code):
                        self.assertEqual(
                            languages.cosmyx_catalogue(root, row).read_bytes(),
                            languages.cosmyx_catalogue(REPO_ROOT, row).read_bytes(),
                        )

    def test_msgfmt_accepts_every_cosmyx_catalogue(self) -> None:
        msgfmt = find_msgfmt()
        if msgfmt is None:
            if os.environ.get("COSMYX_REQUIRE_MSGFMT") == "1":
                self.fail("msgfmt is required (COSMYX_REQUIRE_MSGFMT=1) but not installed")
            self.skipTest("msgfmt (GNU gettext) is not installed; `just languages-msgfmt-docker` runs this check in Docker")
        cosmyx = REPO_ROOT / "localization" / "cosmyx"
        files = [languages.cosmyx_catalogue(REPO_ROOT, row) for row in ROWS if row.source == "Cosmyx"]
        files += [po for po in cosmyx.glob("*/*.po") if po.stem in PLURAL_FORMS]
        with tempfile.TemporaryDirectory() as tmp:
            for po in files:
                with self.subTest(po=po.relative_to(REPO_ROOT).as_posix()):
                    result = subprocess.run(
                        [msgfmt, "--check-format", "--check-header", "-o", str(Path(tmp) / "out.mo"), str(po)],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


POT = '''msgid ""
msgstr ""
"POT-Creation-Date: 2026-01-01 00:00+0000\\n"
"Content-Type: text/plain; charset=UTF-8\\n"

#, c-format
msgid "Kept %d"
msgstr ""

msgid "Seeded"
msgstr ""

msgid "Fuzzy in seed"
msgstr ""

msgid "%1% object"
msgid_plural "%1% objects"
msgstr[0] ""
msgstr[1] ""
'''

SEED = '''msgid ""
msgstr ""
"Language: nl\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Plural-Forms: nplurals=2; plural=(n==1) ? 0 : 1;\\n"

msgid "Seeded"
msgstr "Gezaaid"

#, fuzzy
msgid "Fuzzy in seed"
msgstr "Vaag"

msgid "%1% object"
msgid_plural "%1% objects"
msgstr[0] "%1% object"
msgstr[1] "%1% objecten"

msgid "Kept %d"
msgstr "Uit zaad %d"
'''

EXISTING = '''msgid ""
msgstr ""
"Last-Translator: Someone\\n"
"Language: nl_BE\\n"
"Content-Type: text/plain; charset=UTF-8\\n"

# translator note
msgid "Kept %d"
msgstr "Behouden %d"

msgid "Gone"
msgstr "Weg"
'''


class TreeTests(unittest.TestCase):
    """The commands on a small fake tree."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.row = languages.UiLocale("nl_BE", "DUTCH_BELGIAN", "nl_BE", "Cosmyx", "nl", "Nederlands (België)", False, "Latin", "nplurals=2; plural=(n != 1);")
        self.upstream = languages.UiLocale("nl_NL", "DUTCH", "nl", "Upstream", "", "Nederlands", False, "Latin", "")
        self.rows = [self.row, self.upstream]
        i18n = self.root / "localization" / "i18n"
        write(i18n / "OrcaSlicer.pot", POT)
        write(i18n / "nl" / "OrcaSlicer_nl.po", SEED)
        write(i18n / "en" / "OrcaSlicer_en.po", SEED.replace("Language: nl", "Language: en"))
        write(i18n / "ru" / "OrcaSlicer_ru.po", SEED.replace("Language: nl", "Language: ru"))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def generated(self) -> "g.Catalogue":
        languages.generate(self.root, self.rows)
        return g.read_po(languages.cosmyx_catalogue(self.root, self.row))

    def test_generate_seeds_new_entries_and_keeps_existing_ones(self) -> None:
        write(languages.cosmyx_catalogue(self.root, self.row), EXISTING)
        catalogue = self.generated()
        by_id = {e.msgid: e for e in catalogue.messages()}
        self.assertEqual(list(by_id), ["Kept %d", "Seeded", "Fuzzy in seed", "%1% object"])
        self.assertEqual(by_id["Kept %d"].msgstr, "Behouden %d")
        self.assertIn("# translator note", by_id["Kept %d"].comments)
        self.assertEqual(by_id["Kept %d"].flags, ["c-format"])
        self.assertEqual(by_id["Seeded"].msgstr, "Gezaaid")
        self.assertTrue(by_id["Seeded"].comments[0].startswith(languages.REVIEW_PREFIX))
        self.assertEqual(by_id["Fuzzy in seed"].msgstr, "")
        self.assertEqual(by_id["%1% object"].msgstr_plural, {0: "%1% object", 1: "%1% objecten"})
        self.assertEqual(catalogue.header_field("Last-Translator"), "Someone")
        self.assertEqual(catalogue.header_field("Plural-Forms"), self.row.plural_forms)
        self.assertEqual(catalogue.header_field("Language"), "nl_BE")

    def test_plural_entries_are_not_seeded_across_plural_counts(self) -> None:
        self.row = languages.UiLocale(**{**self.row.__dict__, "plural_forms": "nplurals=3; plural=(n==1 ? 0 : n==2 ? 1 : 2);"})
        self.rows = [self.row, self.upstream]
        entry = {e.msgid: e for e in self.generated().messages()}["%1% object"]
        self.assertEqual(entry.msgstr_plural, {0: "", 1: "", 2: ""})

    def test_install_uninstall_and_drop(self) -> None:
        languages.generate(self.root, self.rows)
        installed = languages.install(self.root, self.rows)
        self.assertEqual(installed, [languages.installed_catalogue(self.root, self.row)])
        self.assertEqual(installed[0].read_bytes(), languages.cosmyx_catalogue(self.root, self.row).read_bytes())
        # Installing again over an identical (not yet grafted) copy is fine.
        languages.install(self.root, self.rows)
        self.assertEqual(languages.dropped_languages(self.root, self.rows), ["ru"])
        self.assertEqual(languages.drop(self.root, self.rows), ["ru"])
        self.assertFalse((self.root / "localization" / "i18n" / "ru").exists())
        self.assertTrue((self.root / "localization" / "i18n" / "en").exists())
        installed[0].write_text("grafted", encoding="utf-8")
        self.assertEqual(languages.uninstall(self.root, self.rows), installed)
        self.assertFalse(installed[0].parent.exists())

    def test_install_never_shadows_another_catalogue(self) -> None:
        languages.generate(self.root, self.rows)
        target = languages.installed_catalogue(self.root, self.row)
        write(target, "not a copy")
        with self.assertRaises(g.PoError):
            languages.install(self.root, self.rows)
        self.assertEqual(target.read_text(encoding="utf-8"), "not a copy")

    def test_install_needs_generated_catalogues(self) -> None:
        with self.assertRaises(g.PoError):
            languages.install(self.root, self.rows)

    def test_sync_features_adds_every_language_and_seeds(self) -> None:
        languages.generate(self.root, self.rows)
        feature = self.root / "localization" / "cosmyx" / "demo"
        write(feature / "messages.pot", 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\nmsgid "Hello"\nmsgstr ""\n')
        write(feature / "nl.po", 'msgid ""\nmsgstr ""\n"Language: nl\\n"\n\nmsgid "Hello"\nmsgstr "Hallo"\n')
        added = languages.sync_features(self.root, self.rows)
        self.assertEqual(added, {"demo": ["en", "nl_BE", "ru"]})
        nl_be = g.read_po(feature / "nl_BE.po")
        self.assertEqual(nl_be.header_field("Plural-Forms"), self.row.plural_forms)
        self.assertEqual(nl_be.messages()[0].msgstr, "Hallo")
        self.assertTrue(nl_be.messages()[0].comments[0].startswith(languages.REVIEW_PREFIX))
        self.assertEqual(g.read_po(feature / "ru.po").messages()[0].msgstr, "")
        self.assertEqual(languages.sync_features(self.root, self.rows), {})

    def test_graft_ignores_the_languages_folder(self) -> None:
        languages.generate(self.root, self.rows)
        cosmyx = self.root / "localization" / "cosmyx"
        self.assertEqual(g.cosmyx_catalogues(cosmyx), {})
        self.assertEqual(set(g.all_languages(self.root / "localization" / "i18n", cosmyx)), {"en", "nl", "nl_BE", "ru"})
        languages.install(self.root, self.rows)
        with self.assertRaises(g.PoError):
            g.all_languages(self.root / "localization" / "i18n", cosmyx)


class WiringTests(unittest.TestCase):
    def test_prepare_action_installs_before_the_graft_and_drops_after(self) -> None:
        text = (REPO_ROOT / ".github" / "actions" / "cosmyx-prepare" / "action.yml").read_text(encoding="utf-8")
        steps = [step.splitlines()[0] for step in text.split("    - name: ")[1:]]
        order = [steps.index(name) for name in (
            "Install the Cosmyx languages", "Graft the Cosmyx translations",
            "Drop the languages Cosmyx does not offer", "Hide the build-time edits from git diff",
        )]
        self.assertEqual(order, sorted(order))
        self.assertEqual(order[-1], len(steps) - 1)
        self.assertIn("-p test_languages.py", text)

    def test_hooks(self) -> None:
        gui = REPO_ROOT / "src" / "slic3r" / "GUI"
        expected = {
            "GUI_App.cpp": [
                '#include "Cosmyx/Languages.hpp" // Cosmyx',
                "const wxLanguageInfo *cosmyx_requested = language_info; // Cosmyx",
                "language_info = Cosmyx::ui_language_info(cosmyx_requested, language_info); // Cosmyx",
            ],
            "Preferences.cpp": [
                '#include "Cosmyx/Languages.hpp" // Cosmyx',
                "Cosmyx::select_ui_languages(language_infos); // Cosmyx",
                "language_name = Cosmyx::ui_language_name(vlist[i], language_name); // Cosmyx",
            ],
        }
        for name, hooks in expected.items():
            text = (gui / name).read_text(encoding="utf-8")
            for hook in hooks:
                with self.subTest(file=name, hook=hook):
                    self.assertEqual(text.count(hook), 1)
        app = (gui / "GUI_App.cpp").read_text(encoding="utf-8")
        # The requested language is captured before upstream refuses the
        # right-to-left ones, and applied after its fallback chain.
        self.assertLess(app.index("cosmyx_requested = language_info"), app.index("which is not supported by OrcaSlicer"))
        self.assertLess(app.index("Cosmyx::ui_language_info("), app.index("const wxLanguageInfo *translation_language_info = language_info;"))
        self.assertGreater(app.index("Cosmyx::ui_language_info("), app.index("language_info = wxLocale::GetLanguageInfo(wxLANGUAGE_ENGLISH_US);"))

    def test_cli(self) -> None:
        result = subprocess.run([sys.executable, str(COSMYX_DIR / "languages.py"), "check"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("24 languages", result.stdout)


if __name__ == "__main__":
    unittest.main()
