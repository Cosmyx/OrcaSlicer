"""Tests of scripts/cosmyx/i18n_graft.py: the graft of the Cosmyx catalogues
into the OrcaSlicer ones."""

from __future__ import annotations

import difflib
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

COSMYX_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = COSMYX_DIR.parents[1]


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, COSMYX_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


g = load_module("i18n_graft")

ORCA_FR = """\
# French translation.
msgid ""
msgstr ""
"Project-Id-Version: Orca Slicer\\n"
"Language: fr\\n"
"Content-Type: text/plain; charset=UTF-8\\n"
"Plural-Forms: nplurals=2; plural=(n==0 || n==1) ? 0 : 1;\\n"

msgid "Shared"
msgstr "Partage Orca"

msgid "Kept"
msgstr "Garde Orca"

#, fuzzy
#| msgid "Old"
msgid "Fuzzy in Orca"
msgstr "Flou Orca"

msgctxt "Camera View"
msgid "Back"
msgstr "Arriere"

msgid "%1% object"
msgid_plural "%1% objects"
msgstr[0] "%1% objet"
msgstr[1] "%1% objets"

#~ msgid "Was removed"
#~ msgstr "Retire"
"""

FEATURE_A_FR = """\
msgid ""
msgstr ""
"Language: fr\\n"
"Plural-Forms: nplurals=2; plural=(n==0 || n==1) ? 0 : 1;\\n"

msgid "Shared"
msgstr "Partage Cosmyx"

#, fuzzy
msgid "Kept"
msgstr "Flou Cosmyx"

msgid "Fuzzy in Orca"
msgstr "Net Cosmyx"

msgctxt "Navigation"
msgid "Back"
msgstr "Retour Cosmyx"

msgid "Only Cosmyx"
msgstr "Seulement Cosmyx"

msgid "Only Cosmyx, untranslated"
msgstr ""

msgid "Was removed"
msgstr "Revenu"

#~ msgid "Cosmyx obsolete"
#~ msgstr "Obsolete"
"""

FEATURE_B_FR = """\
msgid ""
msgstr ""
"Language: fr\\n"

msgid "%1% model"
msgid_plural "%1% models"
msgstr[0] "%1% modele"
msgstr[1] "%1% modeles"

msgid "%1% object"
msgid_plural "%1% objects"
msgstr[0] "%1% objet Cosmyx"
msgstr[1] ""
"""


class TreeCase(unittest.TestCase):
    """A temporary localization/i18n + localization/cosmyx pair."""

    def setUp(self) -> None:
        # Never inherit the job summary of the CI run hosting the tests: main()
        # would append fake graft tables to it.
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("GITHUB_STEP_SUMMARY", None)
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.i18n = self.root / "i18n"
        self.cosmyx = self.root / "cosmyx"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        g.write_text(path, text)
        return path

    def orca(self, language: str, text: str) -> Path:
        return self.write(self.i18n / language / f"OrcaSlicer_{language}.po", text)

    def feature(self, feature: str, language: str, text: str) -> Path:
        return self.write(self.cosmyx / feature / f"{language}.po", text)

    def run_main(self, *args: str) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = g.main(["--i18n-dir", str(self.i18n), "--cosmyx-dir", str(self.cosmyx), *args])
        return code, out.getvalue(), err.getvalue()

    def grafted(self, language: str = "fr") -> dict:
        catalogue = g.read_po(self.i18n / language / f"OrcaSlicer_{language}.po")
        return {e.key: e for e in catalogue.messages()}


class GraftRulesTests(TreeCase):
    def setUp(self) -> None:
        super().setUp()
        self.orca_path = self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", FEATURE_A_FR)
        self.feature("feature-b", "fr", FEATURE_B_FR)
        code, self.out, self.err = self.run_main()
        self.assertEqual(code, 0, self.err)
        self.entries = self.grafted()
        self.text = self.orca_path.read_text(encoding="utf-8")

    def test_translated_cosmyx_entry_replaces_orca(self) -> None:
        self.assertEqual(self.entries[(None, "Shared")].msgstr, "Partage Cosmyx")

    def test_fuzzy_cosmyx_entry_never_replaces_orca(self) -> None:
        self.assertEqual(self.entries[(None, "Kept")].msgstr, "Garde Orca")

    def test_replacing_clears_fuzzy_and_previous_msgid(self) -> None:
        entry = self.entries[(None, "Fuzzy in Orca")]
        self.assertEqual(entry.msgstr, "Net Cosmyx")
        self.assertFalse(entry.fuzzy)
        self.assertNotIn("#| msgid", self.text)

    def test_cosmyx_only_entries_are_appended(self) -> None:
        self.assertEqual(self.entries[(None, "Only Cosmyx")].msgstr, "Seulement Cosmyx")
        self.assertEqual(self.entries[(None, "Only Cosmyx, untranslated")].msgstr, "")

    def test_msgctxt_is_part_of_the_key(self) -> None:
        self.assertEqual(self.entries[("Camera View", "Back")].msgstr, "Arriere")
        self.assertEqual(self.entries[("Navigation", "Back")].msgstr, "Retour Cosmyx")

    def test_plural_entries_keep_their_forms(self) -> None:
        self.assertEqual(self.entries[(None, "%1% model")].msgstr_plural, {0: "%1% modele", 1: "%1% modeles"})
        self.assertIn('msgstr[1] "%1% modeles"', self.text)

    def test_incomplete_plural_does_not_replace_orca(self) -> None:
        self.assertEqual(self.entries[(None, "%1% object")].msgstr_plural, {0: "%1% objet", 1: "%1% objets"})

    def test_obsolete_cosmyx_entries_are_dropped(self) -> None:
        self.assertNotIn("Cosmyx obsolete", self.text)

    def test_obsolete_orca_entry_with_a_grafted_key_is_dropped(self) -> None:
        self.assertEqual(self.entries[(None, "Was removed")].msgstr, "Revenu")
        self.assertNotIn("#~ msgid \"Was removed\"", self.text)
        self.assertEqual(self.text.count('msgid "Was removed"'), 1)

    def test_orca_header_is_kept(self) -> None:
        self.assertTrue(self.text.startswith(ORCA_FR.split("\n\n")[0]))

    def test_counts_are_printed(self) -> None:
        self.assertIn("fr: 2 replaced, 4 appended, 1 appended untranslated, 2 kept OrcaSlicer, 1 dropped obsolete", self.out)


class GraftErrorTests(TreeCase):
    def test_same_msgid_in_two_features_is_an_error_and_writes_nothing(self) -> None:
        path = self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", FEATURE_A_FR)
        self.feature("feature-c", "fr", 'msgid "Only Cosmyx"\nmsgstr "Doublon"\n')
        code, _, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("Only Cosmyx", err)
        self.assertIn("feature-a", err)
        self.assertIn("feature-c", err)
        self.assertEqual(path.read_text(encoding="utf-8"), ORCA_FR)

    def test_same_msgid_twice_in_one_file_is_an_error(self) -> None:
        self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", 'msgid "Twice"\nmsgstr "Un"\n\nmsgid "Twice"\nmsgstr "Deux"\n')
        code, _, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("twice", err)

    def test_same_msgid_with_other_context_is_not_a_duplicate(self) -> None:
        self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", 'msgctxt "A"\nmsgid "Same"\nmsgstr "Un"\n')
        self.feature("feature-c", "fr", 'msgctxt "B"\nmsgid "Same"\nmsgstr "Deux"\n')
        code, _, err = self.run_main()
        self.assertEqual(code, 0, err)

    def test_plural_against_singular_is_an_error(self) -> None:
        path = self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", 'msgid "Shared"\nmsgid_plural "Shareds"\nmsgstr[0] "a"\nmsgstr[1] "b"\n')
        code, _, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("plural", err)
        self.assertEqual(path.read_text(encoding="utf-8"), ORCA_FR)

    def test_an_error_in_a_later_language_writes_no_language(self) -> None:
        fr = self.orca("fr", ORCA_FR)
        self.orca("it", ORCA_FR.replace("Language: fr", "Language: it"))
        self.feature("feature-a", "fr", FEATURE_A_FR)
        self.feature("feature-a", "it", 'msgid "X"\nmsgstr "1"\n')
        self.feature("feature-c", "it", 'msgid "X"\nmsgstr "2"\n')
        code, _, _ = self.run_main()
        self.assertEqual(code, 1)
        self.assertEqual(fr.read_text(encoding="utf-8"), ORCA_FR)

    def test_unparsable_cosmyx_file_is_an_error(self) -> None:
        self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", 'msgid "Broken\nmsgstr ""\n')
        code, _, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("cannot parse", err)

    def test_language_orca_lacks_warns_and_is_skipped(self) -> None:
        self.orca("fr", ORCA_FR)
        self.feature("feature-a", "xx", 'msgid "Only Cosmyx"\nmsgstr "?"\n')
        code, out, err = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("warning", err)
        self.assertIn("'xx'", err)
        self.assertNotIn("xx:", out)
        self.assertFalse((self.i18n / "xx").exists())

    def test_github_actions_annotations(self) -> None:
        self.orca("fr", ORCA_FR)
        self.feature("feature-a", "xx", 'msgid "A"\nmsgstr "?"\n')
        old = os.environ.get("GITHUB_ACTIONS")
        os.environ["GITHUB_ACTIONS"] = "true"
        try:
            _, _, err = self.run_main("--dry-run")
        finally:
            if old is None:
                del os.environ["GITHUB_ACTIONS"]
            else:
                os.environ["GITHUB_ACTIONS"] = old
        self.assertIn("::warning title=Cosmyx graft::", err)


class GraftCliTests(TreeCase):
    def test_dry_run_writes_nothing(self) -> None:
        path = self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", FEATURE_A_FR)
        code, out, _ = self.run_main("--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("fr: 2 replaced, 3 appended, 1 appended untranslated, 1 kept OrcaSlicer", out)
        self.assertEqual(path.read_text(encoding="utf-8"), ORCA_FR)

    def test_summary_is_written_as_markdown(self) -> None:
        self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", FEATURE_A_FR)
        summary = self.root / "summary.md"
        self.run_main("--dry-run", "--summary", str(summary))
        text = summary.read_text(encoding="utf-8")
        self.assertIn("| fr | 2 | 3 | 1 | 1 | 1 |", text)
        self.assertIn("(dry run)", text)

    def test_language_without_cosmyx_files_is_untouched(self) -> None:
        de = self.orca("de", ORCA_FR.replace("Language: fr", "Language: de"))
        self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", FEATURE_A_FR)
        self.run_main()
        self.assertEqual(de.read_text(encoding="utf-8"), ORCA_FR.replace("Language: fr", "Language: de"))

    def test_untranslated_only_graft_keeps_orca_bytes(self) -> None:
        path = self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", 'msgid "Shared"\nmsgstr ""\n')
        self.run_main()
        self.assertEqual(path.read_bytes(), ORCA_FR.encode("utf-8"))

    def test_output_is_lf(self) -> None:
        path = self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", FEATURE_A_FR)
        self.run_main()
        self.assertNotIn(b"\r\n", path.read_bytes())

    def test_crlf_catalogue_grafts_like_lf_and_stays_crlf(self) -> None:
        # A Windows checkout (core.autocrlf) has CRLF catalogues: the graft
        # must give the same text as on LF, written back in CRLF only.
        lf = self.orca("fr", ORCA_FR)
        self.feature("feature-a", "fr", FEATURE_A_FR)
        self.feature("feature-b", "fr", FEATURE_B_FR)
        self.run_main()
        expected = lf.read_bytes()
        lf.write_bytes(ORCA_FR.replace("\n", "\r\n").encode("utf-8"))
        for path in (self.cosmyx / "feature-a" / "fr.po", self.cosmyx / "feature-b" / "fr.po"):
            path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        code, _, err = self.run_main()
        self.assertEqual(code, 0, err)
        data = lf.read_bytes()
        self.assertEqual(data.replace(b"\r\n", b"\n"), expected)
        self.assertEqual(data.count(b"\n"), data.count(b"\r\n"), "mixed line endings")

    def test_crlf_untranslated_only_graft_keeps_orca_bytes(self) -> None:
        path = self.orca("fr", ORCA_FR)
        path.write_bytes(ORCA_FR.replace("\n", "\r\n").encode("utf-8"))
        self.feature("feature-a", "fr", 'msgid "Shared"\r\nmsgstr ""\r\n')
        self.run_main()
        self.assertEqual(path.read_bytes(), ORCA_FR.replace("\n", "\r\n").encode("utf-8"))

    def test_no_cosmyx_folder_is_a_no_op(self) -> None:
        self.orca("fr", ORCA_FR)
        code, _, _ = self.run_main()
        self.assertEqual(code, 0)


class JobSummaryIsolationTests(unittest.TestCase):
    def test_graft_tests_do_not_write_the_ci_job_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.md"
            env = {**os.environ, "GITHUB_STEP_SUMMARY": str(summary)}
            result = subprocess.run(
                [sys.executable, "-m", "unittest", "test_i18n_graft.GraftCliTests", "test_i18n_graft.GraftRulesTests"],
                cwd=Path(__file__).resolve().parent,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(summary.exists() and summary.read_text(encoding="utf-8"), "tests leaked into the job summary")


class PoFormatTests(unittest.TestCase):
    def test_escapes_round_trip(self) -> None:
        value = 'Tab\there "quoted" back\\slash\nnew line'
        lines = g.format_string("msgid", value)
        entry = g.parse_po("\n".join(lines) + '\nmsgstr ""\n').messages()[0]
        self.assertEqual(entry.msgid, value)

    def test_long_strings_wrap_at_79_columns(self) -> None:
        value = " ".join(["word"] * 60)
        lines = g.format_string("msgstr", value)
        self.assertEqual(lines[0], 'msgstr ""')
        self.assertTrue(all(len(line) <= 79 for line in lines))
        self.assertEqual("".join(line[1:-1] for line in lines[1:]), value)

    def test_unicode_is_kept(self) -> None:
        text = 'msgid "Temp ℃"\nmsgstr "温度 ℃"\n'
        entry = g.parse_po(text).messages()[0]
        self.assertEqual(entry.msgstr, "温度 ℃")

    def test_entries_without_blank_line_between(self) -> None:
        text = 'msgid "A"\nmsgstr "a"\nmsgid "B"\nmsgstr "b"\n'
        self.assertEqual([e.msgid for e in g.parse_po(text).messages()], ["A", "B"])

    def test_crlf_input_is_parsed(self) -> None:
        text = 'msgid "A"\r\nmsgstr "a"\r\n'
        self.assertEqual(g.parse_po(text).messages()[0].msgstr, "a")

    def test_line_ending_is_the_dominant_one(self) -> None:
        self.assertEqual(g.line_ending("a\r\nb\r\nc\n"), "\r\n")
        self.assertEqual(g.line_ending("a\nb\nc\r\n"), "\n")
        self.assertEqual(g.line_ending("no newline"), "\n")

    def test_read_po_holds_lf_text_and_remembers_crlf(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.po"
            path.write_bytes(b'msgid "A"\r\nmsgstr "a"\r\n\r\nmsgid "B"\r\nmsgstr "b"\r\n')
            catalogue = g.read_po(path)
            self.assertEqual(catalogue.eol, "\r\n")
            self.assertNotIn("\r", catalogue.render())
            g.write_text(path, catalogue.render(), catalogue.eol)
            self.assertEqual(path.read_bytes(), b'msgid "A"\r\nmsgstr "a"\r\n\r\nmsgid "B"\r\nmsgstr "b"\r\n')

    def test_missing_msgstr_is_an_error(self) -> None:
        with self.assertRaises(g.PoError):
            g.parse_po('msgid "A"\n\nmsgid "B"\nmsgstr ""\n')

    def test_bad_escape_is_an_error(self) -> None:
        with self.assertRaises(g.PoError):
            g.parse_po('msgid "A\\q"\nmsgstr ""\n')


class RealCatalogueTests(unittest.TestCase):
    """The parser on the real OrcaSlicer French catalogue."""

    PATH = REPO_ROOT / "localization" / "i18n" / "fr" / "OrcaSlicer_fr.po"

    def setUp(self) -> None:
        self.text = self.PATH.read_text(encoding="utf-8")
        self.catalogue = g.parse_po(self.text, self.PATH)

    def test_round_trip_is_byte_identical(self) -> None:
        self.assertEqual(self.catalogue.render(), self.text)

    def test_rewritten_entries_parse_back_the_same(self) -> None:
        def summary(catalogue):
            return [(e.key, e.msgid_plural, e.msgstr, e.msgstr_plural, e.flags, e.obsolete) for e in catalogue.entries if e.msgid is not None]

        before = summary(self.catalogue)
        for entry in self.catalogue.entries:
            if entry.msgid is not None:
                entry.touch()
        self.assertEqual(summary(g.parse_po(self.catalogue.render())), before)

    def test_header_and_plurals_are_read(self) -> None:
        self.assertEqual(self.catalogue.header_field("Language"), "fr")
        self.assertTrue(any(e.is_plural for e in self.catalogue.messages()))
        self.assertTrue(any(e.msgctxt for e in self.catalogue.messages()))

    def test_graft_of_one_entry_changes_only_that_entry(self) -> None:
        target = next(e for e in self.catalogue.messages() if not e.is_plural and e.translated)
        cosmyx = {target.key: g.CosmyxEntry("f", Path("f.po"), g.Entry(msgctxt=target.msgctxt, msgid=target.msgid, msgstr="X"))}
        g.graft_language("fr", self.catalogue, cosmyx)
        diff = difflib.ndiff(self.text.splitlines(), self.catalogue.render().splitlines())
        changed = [line for line in diff if line[:1] in "+-"]
        self.assertEqual([line for line in changed if line.startswith("+")], ['+ msgstr "X"'])
        removed = [line for line in changed if line.startswith("-")]
        self.assertTrue(removed and all(line.startswith(("- msgstr ", '- "')) for line in removed), removed)


class CommittedCataloguesTests(unittest.TestCase):
    """The committed localization/cosmyx tree is complete and grafts cleanly."""

    COSMYX = REPO_ROOT / "localization" / "cosmyx"
    I18N = REPO_ROOT / "localization" / "i18n"

    def test_every_feature_has_every_orca_language_and_its_template_msgids(self) -> None:
        catalogues = g.all_languages(self.I18N, self.COSMYX)
        languages = set(catalogues)
        for feature in sorted(p for p in self.COSMYX.iterdir() if p.is_dir() and p.name != g.LANGUAGES_DIR_NAME):
            template = g.read_po(feature / "messages.pot")
            keys = [e.key for e in template.messages()]
            self.assertTrue(keys, f"{feature.name}: empty template")
            self.assertEqual({p.stem for p in feature.glob("*.po")}, languages, feature.name)
            for po in sorted(feature.glob("*.po")):
                catalogue = g.read_po(po)
                self.assertEqual([e.key for e in catalogue.messages()], keys, str(po))
                self.assertEqual(catalogue.header_field("Plural-Forms"), g.read_po(catalogues[po.stem]).header_field("Plural-Forms"), str(po))

    def test_real_tree_grafts_without_error(self) -> None:
        # The CI installs the Cosmyx languages into localization/i18n first
        # (scripts/cosmyx/languages.py install); graft into their committed
        # catalogues here, as a dry run.
        languages = g.all_languages(self.I18N, self.COSMYX)
        report = g.graft(self.I18N, self.COSMYX, languages)
        self.assertEqual(report.warnings, [])
        self.assertEqual(len(report.results), len(languages))


if __name__ == "__main__":
    unittest.main()
