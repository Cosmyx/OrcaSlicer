"""Breaker tests of scripts/cosmyx/i18n_graft.py: PO parsing and graft edge
cases that the reader or the graft gets wrong today.

Every test here reproduces one hole and fails until the graft is fixed.
"""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

COSMYX_DIR = Path(__file__).resolve().parents[1]


def load_module(name: str):
    spec = importlib.util.spec_from_file_location(name, COSMYX_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


g = load_module("i18n_graft")

HEADER = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset={charset}\\n"\n\n'


def header(charset: str = "UTF-8") -> str:
    return HEADER.format(charset=charset)


class TreeMixin:
    def setUp(self) -> None:
        # Keep main() away from the CI job summary of the run hosting the tests.
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("GITHUB_STEP_SUMMARY", None)
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.i18n = self.root / "i18n"
        self.cosmyx = self.root / "cosmyx"
        (self.i18n / "fr").mkdir(parents=True)
        (self.cosmyx / "feature").mkdir(parents=True)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def orca(self, data: bytes) -> Path:
        path = self.i18n / "fr" / "OrcaSlicer_fr.po"
        path.write_bytes(data)
        return path

    def feature(self, data: bytes) -> Path:
        path = self.cosmyx / "feature" / "fr.po"
        path.write_bytes(data)
        return path

    def run_main(self, *extra: str) -> tuple[int, str]:
        err = io.StringIO()
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            code = g.main(["--i18n-dir", str(self.i18n), "--cosmyx-dir", str(self.cosmyx), *extra])
        return code, err.getvalue()


class UnicodeLineBreakInStringTest(unittest.TestCase):
    """A PO string may hold any Unicode character unescaped; only LF ends a
    line for gettext. `str.splitlines` also splits on U+2028, U+0085, form
    feed and the ASCII separators, so a translation holding one of them is
    rejected as an unparsable line."""

    def test_line_separator_characters_inside_msgstr(self) -> None:
        for char in (" ", " ", "\x85", "\x0c", "\x1c"):
            with self.subTest(char=repr(char)):
                text = header() + f'msgid "A"\nmsgstr "a{char}b"\n'
                catalogue = g.parse_po(text)
                self.assertEqual(catalogue.messages()[0].msgstr, f"a{char}b")


class UnescapedQuoteTest(unittest.TestCase):
    """`msgstr "a"b"` is not valid PO (msgfmt rejects it); the greedy
    keyword pattern accepts it and keeps an unescaped quote in the value."""

    def test_unescaped_quote_is_an_error(self) -> None:
        text = header() + 'msgid "A"\nmsgstr "a"b"\n'
        with self.assertRaises(g.PoError):
            g.parse_po(text)


class NoTrailingNewlineTest(TreeMixin, unittest.TestCase):
    """An OrcaSlicer catalogue whose last line has no newline: the appended
    Cosmyx entry is glued to that line (`msgstr "Vieux"msgid "New"`), the
    new entry is lost and the old translation is corrupted."""

    def check(self, eol: str) -> None:
        orca = (header() + 'msgid "Old"\nmsgstr "Vieux"').replace("\n", eol)
        self.orca(orca.encode("utf-8"))
        self.feature((header() + 'msgid "New"\nmsgstr "Neuf"\n').encode("utf-8"))
        code, err = self.run_main()
        self.assertEqual(code, 0, err)
        result = g.read_po(self.i18n / "fr" / "OrcaSlicer_fr.po")
        found = {entry.msgid: entry.msgstr for entry in result.messages()}
        self.assertEqual(found, {"Old": "Vieux", "New": "Neuf"})

    def test_lf_catalogue_without_final_newline(self) -> None:
        self.check("\n")

    def test_crlf_catalogue_without_final_newline(self) -> None:
        self.check("\r\n")


class CharsetTest(TreeMixin, unittest.TestCase):
    def test_graft_into_non_utf8_catalogue_is_refused(self) -> None:
        """The OrcaSlicer catalogue declares ISO-8859-1 (its bytes are ASCII,
        so it decodes): the graft appends UTF-8 text under a header msgfmt
        reads as Latin-1, which garbles every grafted accent. It must refuse
        (or convert), not write silently."""
        self.orca((header("ISO-8859-1") + 'msgid "Old"\nmsgstr "Vieux"\n').encode("ascii"))
        self.feature((header() + 'msgid "New"\nmsgstr "Neuf été"\n').encode("utf-8"))
        with self.assertRaises(g.PoError):
            g.graft(self.i18n, self.cosmyx)

    def test_undecodable_catalogue_is_a_clean_error(self) -> None:
        """A Cosmyx catalogue in Latin-1 bytes: main() must report an error
        and return 1 like any other bad catalogue; today UnicodeDecodeError
        escapes as a traceback."""
        self.orca((header() + 'msgid "Old"\nmsgstr "Vieux"\n').encode("utf-8"))
        self.feature((header("ISO-8859-1") + 'msgid "New"\nmsgstr "Neuf été"\n').encode("latin-1"))
        try:
            code, err = self.run_main("--dry-run")
        except UnicodeDecodeError as error:  # the hole
            self.fail(f"main() raised {error!r} instead of reporting the bad catalogue")
        self.assertEqual(code, 1)
        self.assertIn("fr.po", err)


if __name__ == "__main__":
    unittest.main()
