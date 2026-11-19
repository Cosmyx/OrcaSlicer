"""Tests of scripts/cosmyx/i18n_extract.py: feature mapping, language file
refresh and seeding. The xgettext run itself is covered only where GNU
gettext is installed."""

from __future__ import annotations

import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

COSMYX_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COSMYX_DIR))


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, COSMYX_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


x = load_module("i18n_extract")
g = sys.modules["i18n_graft"]

ORCA_HEADER = """\
msgid ""
msgstr ""
"Language: {lang}\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Plural-Forms: nplurals={n}; plural=0;\\n"
"""

TEMPLATE = """\
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\\n"

#. TRN %s is a version
#, possible-c-format
msgid "Version %s"
msgstr ""

msgid "%1% model"
msgid_plural "%1% models"
msgstr[0] ""
msgstr[1] ""

msgctxt "Menu"
msgid "Open"
msgstr ""
"""


class FeatureMappingTests(unittest.TestCase):
    def test_kebab(self) -> None:
        self.assertEqual(x.kebab("BedTemperatureOff"), "bed-temperature-off")
        self.assertEqual(x.kebab("ChtNozzle"), "cht-nozzle")
        self.assertEqual(x.kebab("GCodeHooks"), "g-code-hooks")
        self.assertEqual(x.kebab("snake_case_name"), "snake-case-name")

    def test_stem_becomes_feature(self) -> None:
        self.assertEqual(x.feature_for(Path("libslic3r/Cosmyx/IroningTemperature.cpp"), set()), "ironing-temperature")

    def test_cosmyx_prefix_is_dropped(self) -> None:
        self.assertEqual(x.feature_for(Path("slic3r/GUI/Cosmyx/logic/CosmyxModels.cpp"), set()), "models")

    def test_known_feature_prefix_wins(self) -> None:
        known = {"models", "models-menu"}
        self.assertEqual(x.feature_for(Path("slic3r/GUI/Cosmyx/CosmyxModelsMenu.cpp"), known), "models")

    def test_prefix_must_end_on_a_word(self) -> None:
        self.assertEqual(x.feature_for(Path("Cosmyx/Modelsx.cpp"), {"models"}), "modelsx")

    def test_explicit_stem_mapping(self) -> None:
        self.assertEqual(x.feature_for(Path("slic3r/GUI/Cosmyx/CosmyxAbout.cpp"), set()), "version")

    def test_sources_are_only_under_cosmyx_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ("libslic3r/Cosmyx/A.cpp", "slic3r/GUI/Cosmyx/logic/B.hpp", "slic3r/GUI/Other.cpp", "libslic3r/Cosmyx/Cosmyx.cmake", "Cosmyx.cpp"):
                (root / rel).parent.mkdir(parents=True, exist_ok=True)
                (root / rel).write_text("", encoding="utf-8")
            found = [p.as_posix() for p in x.cosmyx_sources(root)]
        self.assertEqual(found, ["libslic3r/Cosmyx/A.cpp", "slic3r/GUI/Cosmyx/logic/B.hpp"])


class MergeLanguageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.template = g.parse_po(TEMPLATE)
        self.header = g.Entry(msgid="", msgstr="Language: uk\n")

    def test_new_file_is_untranslated_with_one_form_per_plural(self) -> None:
        merged = x.merge_language(self.template, None, self.header, 4)
        entries = merged.messages()
        self.assertEqual([e.msgid for e in entries], ["Version %s", "%1% model", "Open"])
        self.assertTrue(all(not e.translated for e in entries))
        self.assertEqual(entries[1].msgstr_plural, {0: "", 1: "", 2: "", 3: ""})
        self.assertEqual(merged.header.msgstr, "Language: uk\n")

    def test_template_comments_and_flags_are_copied(self) -> None:
        text = x.merge_language(self.template, None, self.header, 2).render()
        self.assertIn("#. TRN %s is a version\n#, possible-c-format\nmsgid \"Version %s\"", text)
        self.assertIn('msgctxt "Menu"\nmsgid "Open"', text)

    def test_existing_translations_and_translator_comments_are_kept(self) -> None:
        existing = g.parse_po(
            'msgid ""\nmsgstr "Language: fr\\n"\n\n'
            '# AI Translated\nmsgid "Version %s"\nmsgstr "Version %s fr"\n\n'
            '#, fuzzy\nmsgctxt "Menu"\nmsgid "Open"\nmsgstr "Ouvrir"\n\n'
            'msgid "Removed"\nmsgstr "Retire"\n'
        )
        merged = x.merge_language(self.template, existing, self.header, 2)
        entries = {e.key: e for e in merged.messages()}
        self.assertEqual(entries[(None, "Version %s")].msgstr, "Version %s fr")
        self.assertIn("# AI Translated", entries[(None, "Version %s")].comments)
        self.assertTrue(entries[("Menu", "Open")].fuzzy)
        self.assertNotIn((None, "Removed"), entries)
        self.assertEqual(merged.header.msgstr, "Language: fr\n")

    def test_new_header_copies_language_and_plural_forms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            po = Path(tmp) / "OrcaSlicer_uk.po"
            g.write_text(po, ORCA_HEADER.format(lang="uk_UA", n=4))
            header = x.new_header("models", po)
            self.assertEqual(x.plural_count(po), 4)
        self.assertIn("Language: uk_UA\n", header.msgstr)
        self.assertIn("Plural-Forms: nplurals=4; plural=0;\n", header.msgstr)
        self.assertIn("Project-Id-Version: OrcaSlicer Cosmyx models\n", header.msgstr)


class FilterAndWriteTests(unittest.TestCase):
    def test_strings_orca_has_are_left_out(self) -> None:
        template = x.filter_template(g.parse_po(TEMPLATE), {(None, "Version %s")})
        self.assertEqual([e.msgid for e in template.messages()], ["%1% model", "Open"])
        self.assertIsNotNone(template.header)

    def test_write_feature_creates_every_language_and_keeps_pot_when_only_the_date_moved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            i18n = root / "i18n"
            for lang, n in (("fr", 2), ("ja", 1)):
                (i18n / lang).mkdir(parents=True)
                g.write_text(i18n / lang / f"OrcaSlicer_{lang}.po", ORCA_HEADER.format(lang=lang, n=n))
            folder = root / "cosmyx" / "demo"
            dated = TEMPLATE.replace('"Content-Type', '"POT-Creation-Date: 2026-01-01\\n"\n"Content-Type')
            x.write_feature(folder, "demo", g.parse_po(dated), i18n)
            later = dated.replace("2026-01-01", "2026-02-02")
            x.write_feature(folder, "demo", g.parse_po(later), i18n)
            self.assertIn("2026-01-01", (folder / "messages.pot").read_text(encoding="utf-8"))
            self.assertEqual(sorted(p.name for p in folder.glob("*.po")), ["fr.po", "ja.po"])
            ja = g.read_po(folder / "ja.po")
            self.assertEqual(ja.messages()[1].msgstr_plural, {0: ""})


class SeedTests(unittest.TestCase):
    def test_only_translated_non_fuzzy_exact_matches_fill_empty_entries(self) -> None:
        catalogue = g.parse_po('msgid "A"\nmsgstr ""\n\nmsgid "B"\nmsgstr ""\n\nmsgid "C"\nmsgstr "kept"\n\nmsgctxt "x"\nmsgid "D"\nmsgstr ""\n')
        source = g.parse_po('msgid "A"\nmsgstr "a"\n\n#, fuzzy\nmsgid "B"\nmsgstr "b"\n\nmsgid "C"\nmsgstr "c"\n\nmsgid "D"\nmsgstr "d"\n')
        self.assertEqual(x.seed_catalogue(catalogue, source), 1)
        self.assertEqual([e.msgstr for e in catalogue.messages()], ["a", "", "kept", ""])

    @unittest.skipUnless(shutil.which("git"), "git is not installed")
    def test_seed_reads_a_git_ref(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Drop GIT_* variables so an outer repository (hooks, worktrees) is never touched.
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            run = lambda *a: subprocess.run(["git", *a], cwd=root, env=env, check=True, capture_output=True)  # noqa: E731
            run("init", "-q")
            old = root / "localization" / "i18n" / "fr" / "OrcaSlicer_fr.po"
            old.parent.mkdir(parents=True)
            g.write_text(old, 'msgid "Cube"\nmsgstr "Cube fr"\n')
            run("add", ".")
            run("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q", "-m", "old")
            target = root / "localization" / "cosmyx" / "models" / "fr.po"
            target.parent.mkdir(parents=True)
            g.write_text(target, 'msgid "Cube"\nmsgstr ""\n\nmsgid "Other"\nmsgstr ""\n')
            filled = x.seed(root, "HEAD")
            self.assertEqual(filled, {"models": {"fr": 1}})
            self.assertIn('msgstr "Cube fr"', target.read_text(encoding="utf-8"))


class CliTests(unittest.TestCase):
    def test_missing_xgettext_is_reported_clearly(self) -> None:
        err = io.StringIO()
        original = x.shutil.which
        x.shutil.which = lambda name: None
        try:
            with redirect_stderr(err), redirect_stdout(io.StringIO()):
                code = x.main(["extract"])
        finally:
            x.shutil.which = original
        self.assertEqual(code, 2)
        self.assertIn("xgettext (GNU gettext) is not installed", err.getvalue())
        self.assertIn("just i18n-extract-docker", err.getvalue())

    @unittest.skipUnless(shutil.which("xgettext"), "GNU gettext (xgettext) is not installed")
    def test_extract_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src" / "slic3r" / "GUI" / "Cosmyx"
            src.mkdir(parents=True)
            g.write_text(src / "CosmyxDemo.cpp", '// TRN shown in a menu\nauto a = _L("Demo label");\nauto b = _L("Shared upstream");\nauto c = _L_PLURAL("%1% demo", "%1% demos", n);\n')
            (root / "localization" / "i18n" / "fr").mkdir(parents=True)
            g.write_text(root / "localization" / "i18n" / "OrcaSlicer.pot", 'msgid "Shared upstream"\nmsgstr ""\n')
            g.write_text(root / "localization" / "i18n" / "fr" / "OrcaSlicer_fr.po", ORCA_HEADER.format(lang="fr", n=2))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(x.main(["--root", str(root), "extract"]), 0)
            pot = g.read_po(root / "localization" / "cosmyx" / "demo" / "messages.pot")
            self.assertEqual([e.msgid for e in pot.messages()], ["Demo label", "%1% demo"])
            self.assertTrue((root / "localization" / "cosmyx" / "demo" / "fr.po").is_file())


if __name__ == "__main__":
    unittest.main()
