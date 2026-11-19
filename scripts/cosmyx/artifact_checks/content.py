"""What the shipped app carries from the Cosmyx sources (decision 0148).

- translations (T8): every translated, non-fuzzy entry of
  localization/cosmyx/<feature>/<lang>.po of the built commit reads the same
  from the shipped i18n/<lang>/OrcaSlicer.mo (gettext; plurals checked for n=1);
- models (T5): every file of resources/cosmyx/ of the built commit is shipped
  with the same SHA-256;
- names (T6): inventory.names_records.

The .po files are parsed with parse_po of scripts/cosmyx/i18n_graft.py, taken
from the trusted checkout. A part whose sources are not in the built commit is
skipped with the task that brings it.
"""

from __future__ import annotations

import gettext
import importlib.util
import os
import sys
from pathlib import Path

from .records import Record, iter_files, posix_relative, sha256_file

VERSION_INC = Path("version.inc")
VERSION_HEADER = Path("src", "slic3r", "GUI", "Cosmyx", "logic", "CosmyxVersion.hpp")
MAX_LISTED = 20


def find_resources(root: Path) -> Path | None:
    """The shipped resources folder: the one holding i18n/ and profiles/."""
    for folder, dirs, _files in sorted(os.walk(root, followlinks=False)):
        if "i18n" in dirs and "profiles" in dirs:
            return Path(folder)
    return None


def load_script(path: Path, name: str):
    """Import a tool script by path, or None when the trusted checkout lacks it."""
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # Registered first: dataclasses look their module up in sys.modules.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def display_version(tools: Path, subject: Path) -> str | None:
    """The Cosmyx display version of the built commit (T6), or None before T6."""
    if not (subject / VERSION_HEADER).is_file():
        return None
    version = load_script(tools / "scripts" / "cosmyx" / "cosmyx_version.py", "cosmyx_version_for_checks")
    if version is None:
        return None
    return version.display_version(subject)


def expected_translation(entry, translations: gettext.GNUTranslations) -> tuple[str, str]:
    """(expected, shipped) text of one .po entry."""
    if entry.is_plural:
        index = translations.plural(1)
        expected = entry.msgstr_plural.get(index, "")
        if entry.msgctxt is not None:
            shipped = translations.npgettext(entry.msgctxt, entry.msgid, entry.msgid_plural, 1)
        else:
            shipped = translations.ngettext(entry.msgid, entry.msgid_plural, 1)
        return expected, shipped
    if entry.msgctxt is not None:
        return entry.msgstr, translations.pgettext(entry.msgctxt, entry.msgid)
    return entry.msgstr, translations.gettext(entry.msgid)


def translation_records(os_name: str, artifact: str, resources: Path, tools: Path, subject: Path) -> list[Record]:
    cosmyx_dir = subject / "localization" / "cosmyx"
    if not cosmyx_dir.is_dir():
        return [Record(os_name, artifact, "", "translations", "skip", "T8 not merged: no localization/cosmyx")]
    graft = load_script(tools / "scripts" / "cosmyx" / "i18n_graft.py", "i18n_graft_for_checks")
    if graft is None:
        return [Record(os_name, artifact, "", "translations", "skip", "T8 not merged: no i18n_graft.py")]
    by_language: dict[str, list[tuple[str, Path]]] = {}
    for feature in sorted(p for p in cosmyx_dir.iterdir() if p.is_dir()):
        for po in sorted(feature.glob("*.po")):
            by_language.setdefault(po.stem, []).append((feature.name, po))
    records = []
    i18n = resources / "i18n"
    for language, files in sorted(by_language.items()):
        path = f"i18n/{language}/OrcaSlicer.mo"
        entries = []
        for feature, po in files:
            catalogue = graft.parse_po(po.read_text(encoding="utf-8"), po)
            entries += [(feature, e) for e in catalogue.messages() if e.translated and not e.fuzzy]
        if not entries:
            continue
        if not (i18n / language).is_dir():
            records.append(Record(os_name, artifact, path, "translations", "warn",
                                  f"OrcaSlicer ships no {language} catalogue; {len(entries)} Cosmyx entries unused"))
            continue
        mo = i18n / language / "OrcaSlicer.mo"
        if not mo.is_file():
            records.append(Record(os_name, artifact, path, "translations", "fail", "catalogue missing"))
            continue
        with open(mo, "rb") as handle:
            translations = gettext.GNUTranslations(handle)
        wrong = []
        for feature, entry in entries:
            expected, shipped = expected_translation(entry, translations)
            if expected != shipped:
                wrong.append(f"{feature}: {entry.msgid!r}")
        if wrong:
            records.append(Record(os_name, artifact, path, "translations", "fail",
                                  f"{len(wrong)} of {len(entries)} Cosmyx entries not shipped as translated",
                                  {"entries": wrong[:MAX_LISTED]}))
        else:
            records.append(Record(os_name, artifact, path, "translations", "pass",
                                  f"{len(entries)} Cosmyx entries shipped"))
    return records


def model_records(os_name: str, artifact: str, resources: Path, subject: Path) -> list[Record]:
    source = subject / "resources" / "cosmyx"
    if not source.is_dir():
        return [Record(os_name, artifact, "", "models", "skip", "T5 not merged: no resources/cosmyx")]
    missing, different, files = [], [], iter_files(source)
    for file in files:
        rel = posix_relative(file, source)
        shipped = resources / "cosmyx" / Path(*rel.split("/"))
        if not shipped.is_file():
            missing.append(rel)
        elif sha256_file(shipped) != sha256_file(file):
            different.append(rel)
    details = {"missing": missing[:MAX_LISTED], "different": different[:MAX_LISTED], "files": len(files)}
    if missing or different:
        return [Record(os_name, artifact, "cosmyx/", "models", "fail",
                       f"{len(missing)} missing, {len(different)} different of {len(files)} files", details)]
    return [Record(os_name, artifact, "cosmyx/", "models", "pass", f"{len(files)} files shipped unchanged", details)]


def tree_records(os_name: str, artifact: str, tree: Path, tools: Path, subject: Path) -> list[Record]:
    """Translations and models of one unpacked app."""
    resources = find_resources(tree)
    if resources is None:
        return [Record(os_name, artifact, "", check, "fail", "no resources folder (i18n/ and profiles/) in the app")
                for check in ("translations", "models")]
    return translation_records(os_name, artifact, resources, tools, subject) + \
        model_records(os_name, artifact, resources, subject)

