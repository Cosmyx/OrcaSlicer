"""Rename msgids in the gettext catalogues, with the T8 PO reader.

For every message whose msgid (or msgid_plural) is an old text of the rename
table, in the template and in every `<lang>/*.po` of `localization/i18n`:

- the msgid becomes the new text;
- in a `.po`, the upstream name in the translation (msgstr, every plural
  form) becomes CosmoSlice, native spellings included (zh_CN, zh_TW, ko);
- flags are kept as they are: an entry is never marked fuzzy, so a renamed
  string keeps showing its translation.

Untouched entries are written back byte for byte (the T8 reader keeps each
entry's original text). The graft (T8) runs earlier in the prepare step, so
the Cosmyx entries are already in the catalogues.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from .. import BrandingError, relative_posix, repo_path
from .tokens import replace_tokens

CATALOGUE_DIR = "localization/i18n"


def _load_graft():
    if "i18n_graft" in sys.modules:
        return sys.modules["i18n_graft"]
    path = Path(__file__).resolve().parents[2] / "i18n_graft.py"
    spec = importlib.util.spec_from_file_location("i18n_graft", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["i18n_graft"] = module
    spec.loader.exec_module(module)
    return module


graft = _load_graft()


def catalogue_files(root: Path) -> list[str]:
    """The template(s), then every `<lang>/*.po`, as repository-relative paths."""
    base = repo_path(root, CATALOGUE_DIR)
    if not base.is_dir():
        return []
    pots = sorted(base.glob("*.pot"))
    pos = sorted(base.glob("*/*.po"), key=lambda path: path.relative_to(base).as_posix())
    return [relative_posix(root, path) for path in pots + pos]


def language(relative: str) -> str | None:
    """`fr` for localization/i18n/fr/OrcaSlicer_fr.po, None for the template."""
    parts = relative.split("/")
    return parts[-2] if relative.endswith(".po") and len(parts) >= 2 else None


def read(root: Path, relative: str):
    try:
        return graft.read_po(repo_path(root, relative))
    except (graft.PoError, OSError, UnicodeDecodeError) as error:
        raise BrandingError(f"{relative}: {error}") from error


def msgids(catalogue) -> dict:
    """{msgid or msgid_plural: number of active messages carrying it}."""
    found: dict = {}
    for entry in catalogue.messages():
        for text in (entry.msgid, entry.msgid_plural):
            if text is not None:
                found[text] = found.get(text, 0) + 1
    return found


def rename_catalogue(catalogue, mapping: dict, lang: str | None, inflections: dict | None = None) -> int:
    """Rename in place; returns the number of messages changed.

    `inflections` is a `tokens.inflection_map` (None: the committed table)."""
    present = msgids(catalogue)
    for old, new in mapping.items():
        if old in present and new in present:
            raise BrandingError(f"msgid {new!r} already exists next to {old!r}; the rename would duplicate it")
    changed = 0
    for entry in catalogue.messages():
        hit = False
        if entry.msgid in mapping:
            entry.msgid = mapping[entry.msgid]
            hit = True
        if entry.msgid_plural is not None and entry.msgid_plural in mapping:
            entry.msgid_plural = mapping[entry.msgid_plural]
            hit = True
        if not hit:
            continue
        if lang is not None:
            entry.msgstr = replace_tokens(entry.msgstr, lang, inflections=inflections)
            entry.msgstr_plural = {
                index: replace_tokens(text, lang, inflections=inflections) for index, text in entry.msgstr_plural.items()
            }
        entry.touch()
        changed += 1
    return changed


def plan(root: Path, mapping: dict, inflections: dict | None = None) -> dict:
    """{relative path: (new text, messages changed)} for every catalogue that changes."""
    result = {}
    for relative in catalogue_files(root):
        catalogue = read(root, relative)
        try:
            changed = rename_catalogue(catalogue, mapping, language(relative), inflections)
        except BrandingError as error:
            raise BrandingError(f"{relative}: {error}") from error
        if changed:
            result[relative] = (catalogue.render(), changed)
    return result


def renamed_translations(root: Path, msgids: set):
    """(relative, language, msgid, text) of every confirmed translation (msgstr
    and plural forms) of a msgid in `msgids`, in every `<lang>/*.po`."""
    for relative in catalogue_files(root):
        lang = language(relative)
        if lang is None:
            continue
        for entry in read(root, relative).messages():
            if entry.msgid not in msgids or entry.fuzzy:
                continue
            for text in (entry.msgstr, *entry.msgstr_plural.values()):
                if text:
                    yield relative, lang, entry.msgid, text
