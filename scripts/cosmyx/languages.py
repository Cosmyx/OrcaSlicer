"""The UI languages Cosmyx offers (decision 0220).

The table is src/slic3r/GUI/Cosmyx/logic/UiLocaleTable.inc, which the C++ code
expands and this script parses. Each row names the catalogue folder of its
language: an upstream one in localization/i18n, never edited, or a Cosmyx one
in localization/cosmyx/i18n/<folder>/OrcaSlicer_<folder>.po for a language
OrcaSlicer does not ship.

Commands:

- `table`: print the table.
- `generate`: create or refresh the Cosmyx catalogues from
  localization/i18n/OrcaSlicer.pot. Existing translations and translator
  comments are kept; a new entry is copied from the row's seed catalogue when
  that one has a translation, with a `# Needs human review:` comment, and is
  left untranslated otherwise. Run it after upstream regenerates the template.
- `install`: copy the Cosmyx catalogues into localization/i18n, so the upstream
  build scripts (run_gettext.sh/.bat) compile and package them like the
  upstream ones, and the translation graft reaches them. The CI runs it before
  the graft.
- `drop`: delete from localization/i18n the upstream catalogues no row uses
  (English, the source language, is kept), so the build does not package
  them. CI only: the files are tracked, and the prepare action hides the
  deletion from git diff.
- `uninstall`: remove the installed copies again (local use).
- `sync-features`: give every feature catalogue folder of localization/cosmyx a
  <lang>.po for every language that has a catalogue, the Cosmyx ones included,
  without xgettext. `just i18n-extract` does the same as part of a full
  extraction.
- `check`: check the table and the committed catalogues.

Standard library only; shares the PO reader and writer of i18n_graft.py.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import i18n_extract  # noqa: E402
from i18n_graft import LANGUAGES_DIR_NAME, Catalogue, Entry, PoError, all_languages, orca_languages, read_po, write_text  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
TABLE_PATH = Path("src") / "slic3r" / "GUI" / "Cosmyx" / "logic" / "UiLocaleTable.inc"

# Upstream catalogue kept even though no row uses it: English is the source
# language and the fallback of every other one.
KEPT_UPSTREAM = {"en"}

SOURCES = {"Upstream", "Cosmyx"}
SCRIPTS = {"Latin", "Greek", "Cyrillic", "Arabic", "Devanagari", "Han", "Japanese", "Hangul"}

REVIEW_COMMENT = "# Needs human review: copied from the {seed} catalogue, check it reads right for {code}"
REVIEW_PREFIX = "# Needs human review: copied from the "


@dataclass(frozen=True)
class UiLocale:
    code: str
    wx_id: str
    catalog: str
    source: str
    seed: str
    native_name: str
    rtl: bool
    script: str
    plural_forms: str

    @property
    def language(self) -> str:
        return self.code.split("_", 1)[0]


class TableError(Exception):
    """The table cannot be parsed or is inconsistent."""


# --------------------------------------------------------------------------
# Table


_TOKEN = re.compile(r'\s*(?:"((?:[^"\\]|\\.)*)"|([A-Za-z_][A-Za-z0-9_]*)|(,)|(\)))')


def _parse_args(text: str, start: int) -> tuple[list[str | bool], int]:
    """Arguments of one macro call starting after its '(': string literals
    (as str), identifiers (as str) and true/false (as bool)."""
    values: list[str | bool] = []
    pos = start
    expect_value = True
    while True:
        match = _TOKEN.match(text, pos)
        if match is None:
            raise TableError(f"unexpected text at offset {pos}: {text[pos:pos + 30]!r}")
        pos = match.end()
        literal, name, comma, close = match.groups()
        if close is not None:
            if expect_value and values:
                raise TableError("trailing comma in a table row")
            return values, pos
        if comma is not None:
            if expect_value:
                raise TableError("empty argument in a table row")
            expect_value = True
            continue
        if not expect_value:
            raise TableError("missing comma in a table row")
        if literal is not None:
            if "\\" in literal:
                raise TableError("escapes are not allowed in table strings; write the UTF-8 text")
            values.append(literal)
        elif name in ("true", "false"):
            values.append(name == "true")
        else:
            values.append(name)
        expect_value = False


def parse_table(text: str) -> list[UiLocale]:
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("COSMYX_UI_LOCALE("):
            continue
        values, end = _parse_args(stripped, len("COSMYX_UI_LOCALE("))
        if stripped[end:].strip():
            raise TableError(f"text after a table row: {stripped[end:]!r}")
        if len(values) != 9:
            raise TableError(f"a table row has {len(values)} columns instead of 9: {stripped}")
        code, wx_id, catalog, source, seed, name, rtl, script, plural = values
        if not isinstance(rtl, bool) or any(isinstance(v, bool) for v in (code, wx_id, catalog, source, seed, name, script, plural)):
            raise TableError(f"wrong column types: {stripped}")
        rows.append(UiLocale(code, wx_id, catalog, source, seed, name, rtl, script, plural))
    return rows


def load_table(root: Path = REPO_ROOT) -> list[UiLocale]:
    return parse_table((root / TABLE_PATH).read_text(encoding="utf-8"))


def table_errors(rows: list[UiLocale]) -> list[str]:
    """Rules every row keeps; the C++ code relies on them too."""
    errors = []
    codes = [row.code for row in rows]
    if codes != sorted(codes):
        errors.append("rows are not in code order")
    if len(set(codes)) != len(codes):
        errors.append("a code is listed twice")
    catalogs = [row.catalog for row in rows]
    if len(set(catalogs)) != len(catalogs):
        errors.append("two rows share a catalogue folder")
    for row in rows:
        where = row.code
        if not re.fullmatch(r"[a-z]{2,3}_[A-Z]{2}", row.code):
            errors.append(f"{where}: code is not language_REGION")
        if not re.fullmatch(r"[A-Z][A-Z_]*", row.wx_id):
            errors.append(f"{where}: wx id {row.wx_id!r} is not a wxLanguage name")
        if row.source not in SOURCES:
            errors.append(f"{where}: unknown source {row.source!r}")
        if row.script not in SCRIPTS:
            errors.append(f"{where}: unknown script {row.script!r}")
        if not row.native_name:
            errors.append(f"{where}: no native name")
        if row.catalog.split("_", 1)[0] != row.language:
            errors.append(f"{where}: catalogue {row.catalog!r} is another language")
        if row.source == "Cosmyx":
            if row.catalog != row.code:
                errors.append(f"{where}: a Cosmyx catalogue folder is named after its code")
            if not re.fullmatch(r"nplurals=\d+; plural=.+;", row.plural_forms):
                errors.append(f"{where}: Cosmyx catalogue without valid plural forms")
        else:
            if row.plural_forms or row.seed:
                errors.append(f"{where}: an upstream catalogue takes no plural forms or seed")
        if row.rtl != (row.script == "Arabic"):
            errors.append(f"{where}: right-to-left flag does not match its script")
    return errors


# --------------------------------------------------------------------------
# Paths


def i18n_dir(root: Path) -> Path:
    return root / "localization" / "i18n"


def cosmyx_dir(root: Path) -> Path:
    return root / "localization" / "cosmyx"


def cosmyx_catalogue(root: Path, row: UiLocale) -> Path:
    return cosmyx_dir(root) / LANGUAGES_DIR_NAME / row.catalog / f"OrcaSlicer_{row.catalog}.po"


def installed_catalogue(root: Path, row: UiLocale) -> Path:
    return i18n_dir(root) / row.catalog / f"OrcaSlicer_{row.catalog}.po"


def dropped_languages(root: Path, rows: list[UiLocale]) -> list[str]:
    """Upstream catalogues no row uses, English kept."""
    used = {row.catalog for row in rows if row.source == "Upstream"} | KEPT_UPSTREAM
    added = {row.catalog for row in rows if row.source == "Cosmyx"}
    return sorted(set(orca_languages(i18n_dir(root))) - used - added)


# --------------------------------------------------------------------------
# Generation


def nplurals(plural_forms: str | None) -> int:
    match = re.search(r"nplurals\s*=\s*(\d+)", plural_forms or "")
    return int(match.group(1)) if match else 2


def header_entry(row: UiLocale, template: Catalogue, existing: Catalogue | None) -> Entry:
    def keep(name: str, default: str) -> str:
        value = existing.header_field(name) if existing else None
        return default if value is None else value

    created = template.header_field("POT-Creation-Date") or ""
    fields = [
        ("Project-Id-Version", keep("Project-Id-Version", "OrcaSlicer")),
        ("Report-Msgid-Bugs-To", ""),
        ("POT-Creation-Date", created),
        ("PO-Revision-Date", keep("PO-Revision-Date", created)),
        ("Last-Translator", keep("Last-Translator", "")),
        ("Language-Team", keep("Language-Team", "")),
        ("Language", row.code),
        ("MIME-Version", "1.0"),
        ("Content-Type", "text/plain; charset=UTF-8"),
        ("Content-Transfer-Encoding", "8bit"),
        ("Plural-Forms", row.plural_forms),
    ]
    return Entry(msgid="", msgstr="".join(f"{name}: {value}\n" for name, value in fields))


def build_catalogue(row: UiLocale, template: Catalogue, existing: Catalogue | None, seed: Catalogue | None) -> Catalogue:
    """The Cosmyx catalogue of a row: template order, existing translations
    kept, the rest seeded or untranslated."""
    count = nplurals(row.plural_forms)
    old = {e.key: e for e in existing.messages()} if existing else {}
    seeded = {e.key: e for e in seed.messages()} if seed else {}
    seed_count = nplurals(seed.header_field("Plural-Forms")) if seed else 0
    entries = [header_entry(row, template, existing)]
    for source in template.messages():
        entry = Entry(
            comments=[c for c in source.comments if not c.startswith("# ")],
            flags=[f for f in source.flags if f != "fuzzy"],
            msgctxt=source.msgctxt,
            msgid=source.msgid,
            msgid_plural=source.msgid_plural,
        )
        if source.is_plural:
            entry.msgstr_plural = {i: "" for i in range(count)}
        previous = old.get(source.key)
        donor = seeded.get(source.key)
        if previous is not None and previous.is_plural == source.is_plural:
            entry.comments = [c for c in previous.comments if c.startswith("# ")] + entry.comments
            if previous.fuzzy:
                entry.flags.append("fuzzy")
            entry.msgstr = previous.msgstr
            if source.is_plural:
                entry.msgstr_plural = {i: previous.msgstr_plural.get(i, "") for i in range(count)}
        elif (
            donor is not None
            and donor.is_plural == source.is_plural
            and donor.translated
            and not donor.fuzzy
            and (not source.is_plural or seed_count == count)
        ):
            entry.comments = [REVIEW_COMMENT.format(seed=row.seed, code=row.code)] + entry.comments
            entry.msgstr = donor.msgstr
            if source.is_plural:
                entry.msgstr_plural = {i: donor.msgstr_plural.get(i, "") for i in range(count)}
        entries.append(entry)
    return Catalogue(entries=entries)


def generate(root: Path, rows: list[UiLocale]) -> dict[str, tuple[int, int]]:
    """Write every Cosmyx catalogue. Returns code -> (translated, seeded)."""
    template = read_po(i18n_dir(root) / "OrcaSlicer.pot")
    counts = {}
    for row in rows:
        if row.source != "Cosmyx":
            continue
        target = cosmyx_catalogue(root, row)
        existing = read_po(target) if target.is_file() else None
        seed = read_po(i18n_dir(root) / row.seed / f"OrcaSlicer_{row.seed}.po") if row.seed else None
        catalogue = build_catalogue(row, template, existing, seed)
        target.parent.mkdir(parents=True, exist_ok=True)
        write_text(target, catalogue.render())
        messages = catalogue.messages()
        counts[row.code] = (
            sum(1 for e in messages if e.translated),
            sum(1 for e in messages if any(c.startswith(REVIEW_PREFIX) for c in e.comments)),
        )
    return counts


# --------------------------------------------------------------------------
# Build-time install and drop


def install(root: Path, rows: list[UiLocale]) -> list[Path]:
    """Copy the Cosmyx catalogues into localization/i18n. A catalogue already
    there with other content is an error, checked before anything is copied:
    it would be an upstream catalogue, which Cosmyx never shadows."""
    pairs = [(cosmyx_catalogue(root, row), installed_catalogue(root, row)) for row in rows if row.source == "Cosmyx"]
    for source, target in pairs:
        if not source.is_file():
            raise PoError(f"missing Cosmyx catalogue {source}; run `just languages-generate`")
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise PoError(f"{target} exists with other content; it is not a Cosmyx copy")
    for source, target in pairs:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return [target for _, target in pairs]


def uninstall(root: Path, rows: list[UiLocale]) -> list[Path]:
    """Remove the installed copies, grafted or not, and their folders when
    nothing else is left in them."""
    removed = []
    for row in rows:
        if row.source != "Cosmyx":
            continue
        target = installed_catalogue(root, row)
        if target.is_file():
            target.unlink()
            removed.append(target)
        if target.parent.is_dir() and not any(target.parent.iterdir()):
            target.parent.rmdir()
    return removed


def drop(root: Path, rows: list[UiLocale]) -> list[str]:
    """Delete the catalogues of the languages no row uses from
    localization/i18n, so the build neither compiles nor packages them."""
    dropped = dropped_languages(root, rows)
    for language in dropped:
        folder = i18n_dir(root) / language
        (folder / f"OrcaSlicer_{language}.po").unlink()
        if not any(folder.iterdir()):
            folder.rmdir()
    return dropped


# --------------------------------------------------------------------------
# Feature catalogues


def seed_feature(catalogue: Catalogue, seed: Catalogue, row: UiLocale) -> None:
    """Copy the translated entries of a seed feature catalogue, marked for review."""
    donors = {e.key: e for e in seed.messages() if e.translated and not e.fuzzy}
    for entry in catalogue.messages():
        donor = donors.get(entry.key)
        if donor is None or donor.is_plural != entry.is_plural or entry.translated:
            continue
        if entry.is_plural and sorted(donor.msgstr_plural) != sorted(entry.msgstr_plural):
            continue
        entry.comments = [REVIEW_COMMENT.format(seed=row.seed, code=row.code)] + entry.comments
        entry.msgstr = donor.msgstr
        entry.msgstr_plural = dict(donor.msgstr_plural)
        entry.touch()


def sync_features(root: Path, rows: list[UiLocale]) -> dict[str, list[str]]:
    """Add the missing <lang>.po of every feature folder; the one of a seeded
    Cosmyx language starts from the seed language's file of that feature.
    Returns feature -> languages added."""
    languages = all_languages(i18n_dir(root), cosmyx_dir(root))
    seeds = {row.catalog: row for row in rows if row.source == "Cosmyx" and row.seed}
    added: dict[str, list[str]] = {}
    for folder in sorted(p for p in cosmyx_dir(root).iterdir() if p.is_dir() and p.name != LANGUAGES_DIR_NAME):
        pot = folder / "messages.pot"
        if not pot.is_file():
            continue
        template = read_po(pot)
        for language, catalogue in sorted(languages.items()):
            target = folder / f"{language}.po"
            if target.exists():
                continue
            header = i18n_extract.new_header(folder.name, catalogue)
            merged = i18n_extract.merge_language(template, None, header, i18n_extract.plural_count(catalogue))
            row = seeds.get(language)
            if row is not None and (folder / f"{row.seed}.po").is_file():
                seed_feature(merged, read_po(folder / f"{row.seed}.po"), row)
            write_text(target, merged.render())
            added.setdefault(folder.name, []).append(language)
    return added


# --------------------------------------------------------------------------
# Checks


def check(root: Path, rows: list[UiLocale]) -> list[str]:
    errors = table_errors(rows)
    upstream = orca_languages(i18n_dir(root))
    template_keys = [e.key for e in read_po(i18n_dir(root) / "OrcaSlicer.pot").messages()]
    for row in rows:
        if row.source == "Upstream":
            if row.catalog not in upstream:
                errors.append(f"{row.code}: no upstream catalogue {row.catalog}")
            continue
        if row.catalog in upstream:
            errors.append(f"{row.code}: Cosmyx catalogue {row.catalog} shadows an upstream one")
        if row.seed and row.seed not in upstream:
            errors.append(f"{row.code}: seed {row.seed} is not an upstream catalogue")
        path = cosmyx_catalogue(root, row)
        if not path.is_file():
            errors.append(f"{row.code}: missing {path.relative_to(root).as_posix()}")
            continue
        catalogue = read_po(path)
        if catalogue.header_field("Language") != row.code:
            errors.append(f"{row.code}: header Language is not {row.code}")
        if catalogue.header_field("Plural-Forms") != row.plural_forms:
            errors.append(f"{row.code}: header Plural-Forms differs from the table")
        if [e.key for e in catalogue.messages()] != template_keys:
            errors.append(f"{row.code}: msgids differ from OrcaSlicer.pot; run `just languages-generate`")
        count = nplurals(row.plural_forms)
        bad = [e.msgid for e in catalogue.messages() if e.is_plural and sorted(e.msgstr_plural) != list(range(count))]
        if bad:
            errors.append(f"{row.code}: {len(bad)} plural entries without exactly {count} forms")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the Cosmyx UI languages (decision 0220).")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this checkout)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (
        ("table", "print the table"),
        ("generate", "create or refresh localization/cosmyx/i18n from OrcaSlicer.pot"),
        ("install", "copy the Cosmyx catalogues into localization/i18n (build time)"),
        ("uninstall", "remove the copies install made"),
        ("drop", "delete the unused upstream catalogues from localization/i18n (CI only)"),
        ("sync-features", "add the missing <lang>.po of every feature catalogue folder"),
        ("check", "check the table and the Cosmyx catalogues"),
    ):
        sub.add_parser(name, help=text)
    args = parser.parse_args(argv)
    root = args.root

    try:
        rows = load_table(root)
        if args.command == "table":
            for row in rows:
                flags = " rtl" if row.rtl else ""
                print(f"{row.code}\t{row.catalog}\t{row.source}{' seed ' + row.seed if row.seed else ''}\t{row.script}{flags}\t{row.native_name}")
        elif args.command == "generate":
            for code, (translated, seeded) in generate(root, rows).items():
                print(f"{code}: {translated} translated, {seeded} copied from the seed")
        elif args.command == "install":
            for path in install(root, rows):
                print(f"installed {path.relative_to(root).as_posix()}")
        elif args.command == "uninstall":
            print(f"removed {len(uninstall(root, rows))} installed catalogue(s)")
        elif args.command == "drop":
            print("dropped: " + (", ".join(drop(root, rows)) or "none"))
        elif args.command == "sync-features":
            added = sync_features(root, rows)
            for feature, languages in added.items():
                print(f"{feature}: added {', '.join(languages)}")
            if not added:
                print("Every feature catalogue folder has every language.")
        else:
            errors = check(root, rows)
            for error in errors:
                print(f"error: {error}", file=sys.stderr)
            if errors:
                return 1
            print(f"{len(rows)} languages, catalogues OK")
    except (TableError, PoError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
