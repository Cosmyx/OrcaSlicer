"""content: translations against a .mo written at runtime, models, the display
version, with a stand-in i18n_graft.parse_po (and the real one once T8 is in)."""

from __future__ import annotations

import struct
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

COSMYX_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COSMYX_DIR))

from artifact_checks import content  # noqa: E402

# A small stand-in with the interface content.py uses from i18n_graft.py:
# parse_po(text, path) -> catalogue with messages(); entries carry msgctxt,
# msgid, msgid_plural, msgstr, msgstr_plural, is_plural, translated, fuzzy.
# Like the real file it uses `from __future__ import annotations`, whose string
# annotations make dataclasses look the module up in sys.modules.
STUB_GRAFT = textwrap.dedent('''
    from __future__ import annotations

    import re
    from dataclasses import dataclass, field

    @dataclass
    class Entry:
        flags: list = field(default_factory=list)
        msgctxt: object = None
        msgid: object = None
        msgid_plural: object = None
        msgstr: str = ""
        msgstr_plural: dict = field(default_factory=dict)

        @property
        def is_plural(self):
            return self.msgid_plural is not None

        @property
        def fuzzy(self):
            return "fuzzy" in self.flags

        @property
        def translated(self):
            if self.is_plural:
                return bool(self.msgstr_plural) and all(self.msgstr_plural.values())
            return self.msgstr != ""

    class Catalogue:
        def __init__(self, entries):
            self.entries = entries

        def messages(self):
            return [e for e in self.entries if e.msgid]

    def parse_po(text, path=None):
        entries, current = [], Entry()
        for line in text.splitlines() + [""]:
            if not line.strip():
                if current.msgid is not None:
                    entries.append(current)
                current = Entry()
                continue
            if line.startswith("#,"):
                current.flags += [f.strip() for f in line[2:].split(",")]
                continue
            key, value = re.match(r'^(\\S+) "(.*)"$', line).groups()
            value = value.replace("\\\\n", "\\n")
            if key.startswith("msgstr["):
                current.msgstr_plural[int(key[7:-1])] = value
            else:
                setattr(current, key, value)
        return Catalogue(entries)
''')


def write_mo(path: Path, messages: dict[str, str], plural_forms: str = "nplurals=2; plural=(n > 1);") -> None:
    """A GNU .mo catalogue (no hash table)."""
    messages = dict(messages)
    messages[""] = f"Content-Type: text/plain; charset=UTF-8\nPlural-Forms: {plural_forms}\n"
    keys = sorted(messages)
    ids = [k.encode("utf-8") for k in keys]
    strs = [messages[k].encode("utf-8") for k in keys]
    count = len(keys)
    start = 7 * 4 + count * 16
    offsets_ids, offsets_strs, blob = [], [], b""
    for data in ids:
        offsets_ids.append((len(data), start + len(blob)))
        blob += data + b"\0"
    for data in strs:
        offsets_strs.append((len(data), start + len(blob)))
        blob += data + b"\0"
    out = struct.pack("<7I", 0x950412DE, 0, count, 28, 28 + count * 8, 0, 0)
    for length, offset in offsets_ids + offsets_strs:
        out += struct.pack("<2I", length, offset)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out + blob)


FR_PO = textwrap.dedent('''
    msgid ""
    msgstr "Language: fr\\n"

    msgid "Nozzle"
    msgstr "Buse"

    msgctxt "Camera View"
    msgid "Back"
    msgstr "Arrière"

    msgid "%d plate"
    msgid_plural "%d plates"
    msgstr[0] "%d plateau"
    msgstr[1] "%d plateaux"

    #, fuzzy
    msgid "Fuzzy one"
    msgstr "Flou"

    msgid "Untranslated"
    msgstr ""
''')


class TranslationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.tools, self.subject, self.resources = root / "tools", root / "subject", root / "app" / "resources"
        graft = self.tools / "scripts" / "cosmyx" / "i18n_graft.py"
        graft.parent.mkdir(parents=True)
        graft.write_text(STUB_GRAFT, encoding="utf-8")
        po = self.subject / "localization" / "cosmyx" / "cht-nozzle" / "fr.po"
        po.parent.mkdir(parents=True)
        po.write_text(FR_PO, encoding="utf-8")
        (self.resources / "profiles").mkdir(parents=True)
        self.good = {"Nozzle": "Buse", "Camera View\x04Back": "Arrière",
                     "%d plate\x00%d plates": "%d plateau\x00%d plateaux"}

    def records(self):
        return content.translation_records("linux", "app", self.resources, self.tools, self.subject)

    def test_shipped_catalogue_passes(self) -> None:
        write_mo(self.resources / "i18n" / "fr" / "OrcaSlicer.mo", self.good)
        records = self.records()
        self.assertEqual([(r.path, r.status) for r in records], [("i18n/fr/OrcaSlicer.mo", "pass")])
        self.assertIn("3 Cosmyx entries", records[0].reason)

    def test_context_and_plural_mismatches_fail(self) -> None:
        for key, wrong in (("Camera View\x04Back", "Retour"), ("%d plate\x00%d plates", "%d plaque\x00%d plaques"),
                           ("Nozzle", "Bec")):
            with self.subTest(key=key):
                messages = dict(self.good)
                messages[key] = wrong
                write_mo(self.resources / "i18n" / "fr" / "OrcaSlicer.mo", messages)
                record = self.records()[0]
                self.assertEqual(record.status, "fail")
                self.assertEqual(len(record.details["entries"]), 1)

    def test_missing_entry_fails(self) -> None:
        messages = dict(self.good)
        del messages["Camera View\x04Back"]
        write_mo(self.resources / "i18n" / "fr" / "OrcaSlicer.mo", messages)
        self.assertEqual(self.records()[0].status, "fail")

    def test_plural_index_follows_the_catalogue(self) -> None:
        # French: n=1 takes form 0 whatever the plural rule says about n > 1.
        write_mo(self.resources / "i18n" / "fr" / "OrcaSlicer.mo", self.good, "nplurals=2; plural=(n==0 || n==1) ? 0 : 1;")
        self.assertEqual(self.records()[0].status, "pass")

    def test_missing_mo_fails_and_unshipped_language_warns(self) -> None:
        (self.resources / "i18n" / "fr").mkdir(parents=True)
        self.assertEqual(self.records()[0].status, "fail")
        (self.resources / "i18n" / "fr").rmdir()
        self.assertEqual(self.records()[0].status, "warn")

    def test_skips_before_t8(self) -> None:
        records = content.translation_records("linux", "app", self.resources, self.tools, self.subject / "none")
        self.assertEqual(records[0].status, "skip")
        self.assertIn("T8", records[0].reason)
        records = content.translation_records("linux", "app", self.resources, self.tools / "none", self.subject)
        self.assertIn("T8", records[0].reason)

    @unittest.skipUnless((COSMYX_DIR / "i18n_graft.py").is_file(), "T8 (i18n_graft.py) not merged on this branch")
    def test_with_the_real_parse_po(self) -> None:
        write_mo(self.resources / "i18n" / "fr" / "OrcaSlicer.mo", self.good)
        records = content.translation_records("linux", "app", self.resources, COSMYX_DIR.parents[1], self.subject)
        self.assertEqual(records[0].status, "pass")


class ModelTests(unittest.TestCase):
    def test_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "subject" / "resources" / "cosmyx" / "models"
            shipped = root / "res" / "cosmyx" / "models"
            source.mkdir(parents=True)
            shipped.mkdir(parents=True)
            (source / "cube.3mf").write_bytes(b"cube")
            (shipped / "cube.3mf").write_bytes(b"cube")
            self.assertEqual(content.model_records("macos", "a", root / "res", root / "subject")[0].status, "pass")
            (shipped / "cube.3mf").write_bytes(b"other")
            (source / "extra.stl").write_bytes(b"x")
            record = content.model_records("macos", "a", root / "res", root / "subject")[0]
            self.assertEqual(record.status, "fail")
            self.assertEqual((record.details["missing"], record.details["different"]), (["models/extra.stl"], ["models/cube.3mf"]))
            self.assertEqual(content.model_records("macos", "a", root / "res", root / "none")[0].status, "skip")

    def test_find_resources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            res = root / "OrcaSlicer.app" / "Contents" / "Resources"
            (res / "i18n").mkdir(parents=True)
            (res / "profiles").mkdir()
            self.assertEqual(content.find_resources(root), res)
            self.assertIsNone(content.find_resources(res / "i18n"))
            records = content.tree_records("macos", "a", res / "i18n", root, root)
            self.assertEqual({r.status for r in records}, {"fail"})


class VersionTests(unittest.TestCase):
    def test_display_version_uses_the_tool_script(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "tools" / "scripts" / "cosmyx" / "cosmyx_version.py"
            script.parent.mkdir(parents=True)
            script.write_text("def display_version(root):\n    return 'v-' + root.name\n", encoding="utf-8")
            subject = root / "subject"
            self.assertIsNone(content.display_version(root / "tools", subject))
            header = subject / content.VERSION_HEADER
            header.parent.mkdir(parents=True)
            header.write_text("inline constexpr int patch_version = 8;\n", encoding="utf-8")
            self.assertEqual(content.display_version(root / "tools", subject), "v-subject")


if __name__ == "__main__":
    unittest.main()
