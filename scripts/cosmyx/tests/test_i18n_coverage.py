"""Tests of scripts/cosmyx/i18n_coverage.py, plus the coverage of the
repository catalogues, enforced only with COSMYX_I18N_STRICT=1 (decision 0085:
feature branches translate French only, and the per-language pass fills the
rest later, so a strict check would fail every feature branch until then)."""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
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


c = load_module("i18n_coverage")

HEADER = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n\n'

CATALOGUE = HEADER + """\
msgid "Done"
msgstr "Fait"

msgid "Empty"
msgstr ""

msgid "Same"
msgstr "Same"

#, fuzzy
msgid "Fuzzy"
msgstr "Flou"

msgid "%1% model"
msgid_plural "%1% models"
msgstr[0] "%1% modèle"
msgstr[1] ""

msgid "CHT"
msgstr "CHT"

msgid "Brand"
msgstr ""
"""


class CoverageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.cosmyx = self.root / "localization" / "cosmyx"
        for language in ("fr", "en", "en_GB", "de"):
            folder = self.cosmyx / "demo"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{language}.po").write_text(CATALOGUE, encoding="utf-8", newline="\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_every_kind_of_gap_is_reported_and_english_is_skipped(self) -> None:
        gaps, checked = c.coverage(self.cosmyx, {"*": {"CHT"}, "fr": {"Brand"}})
        found = {(g.language, g.reason, g.msgid) for g in gaps}
        self.assertEqual(checked, 14)
        self.assertIn(("fr", "untranslated", "Empty"), found)
        self.assertIn(("fr", "same as source", "Same"), found)
        self.assertIn(("fr", "fuzzy", "Fuzzy"), found)
        self.assertIn(("fr", "untranslated", "%1% model"), found)
        self.assertNotIn("Done", {g.msgid for g in gaps})
        self.assertNotIn("CHT", {g.msgid for g in gaps})
        # Brand is allowed for French only.
        self.assertNotIn(("fr", "untranslated", "Brand"), found)
        self.assertIn(("de", "untranslated", "Brand"), found)
        self.assertFalse({g.language for g in gaps} & {"en", "en_GB"})

    def test_language_filter(self) -> None:
        gaps, _ = c.coverage(self.cosmyx, {}, {"de"})
        self.assertEqual({g.language for g in gaps}, {"de"})

    def test_report_exits_zero_unless_strict(self) -> None:
        with redirect_stdout(io.StringIO()) as out:
            self.assertEqual(c.main(["--root", str(self.root)]), 0)
        self.assertIn("demo/fr.po:", out.getvalue())
        self.assertIn("missing of", out.getvalue())
        with redirect_stdout(io.StringIO()):
            self.assertEqual(c.main(["--root", str(self.root), "--strict"]), 1)

    def test_strict_passes_when_complete(self) -> None:
        folder = self.cosmyx / "demo"
        for po in folder.glob("*.po"):
            po.write_text(HEADER + 'msgid "Done"\nmsgstr "Fait"\n', encoding="utf-8", newline="\n")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(c.main(["--root", str(self.root), "--strict"]), 0)

    def test_allow_file_is_valid(self) -> None:
        allow = c.load_allow(c.ALLOW_FILE)
        self.assertIn("CHT", allow["*"])


class RepositoryCoverageTests(unittest.TestCase):
    def test_repository_catalogues_are_translated(self) -> None:
        gaps, _ = c.coverage(REPO_ROOT / "localization" / "cosmyx", c.load_allow(c.ALLOW_FILE))
        if os.environ.get("COSMYX_I18N_STRICT") != "1":
            self.skipTest(f"{len(gaps)} translations missing (just i18n-coverage); enforced with COSMYX_I18N_STRICT=1")
        self.assertEqual([], [f"{g.feature}/{g.language}: {g.reason}: {g.msgid}" for g in gaps])


if __name__ == "__main__":
    unittest.main()
