"""Graft the Cosmyx translation catalogues into the OrcaSlicer ones.

The Cosmyx strings live in per-feature catalogues under localization/cosmyx
(`<feature>/messages.pot` and `<feature>/<lang>.po`), outside the upstream
localization/i18n folder, so that upstream merges never conflict with them.
OrcaSlicer loads a single gettext catalogue, built from
localization/i18n/<lang>/OrcaSlicer_<lang>.po, so the CI merges the Cosmyx
entries into those files right before the build compiles them.

Rules, for each language, with an entry keyed by (msgctxt, msgid):

- A translated, non-fuzzy Cosmyx entry replaces the OrcaSlicer translation of
  the same key, and the result is not fuzzy.
- A fuzzy or untranslated Cosmyx entry never replaces an OrcaSlicer one.
- A Cosmyx key OrcaSlicer does not have is appended (untranslated and fuzzy
  entries are appended as they are; the compiler skips them).
- Obsolete (#~) Cosmyx entries are ignored. An obsolete OrcaSlicer entry with
  the key of a grafted entry is dropped, so the key is never defined twice.
- Plural entries keep their forms. A singular entry on one side and a plural
  one on the other is an error.
- The OrcaSlicer header is kept as it is.
- The same key in two features, or twice in one file, is an error.
- A Cosmyx language that OrcaSlicer does not ship is a warning and is skipped.

Every check runs before any file is written, so an error leaves the tree as it
was. Untouched OrcaSlicer entries are written back byte for byte.

The graft rewrites localization/i18n in place: it is meant for CI. Locally,
`just i18n-ungraft` restores the committed files.

Standard library only, so it runs on every CI leg without a pip install.
"""

from __future__ import annotations

import argparse
import copy
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_I18N_DIR = REPO_ROOT / "localization" / "i18n"
DEFAULT_COSMYX_DIR = REPO_ROOT / "localization" / "cosmyx"

# Width gettext wraps string lines at.
WRAP_WIDTH = 79


class PoError(Exception):
    """A catalogue cannot be parsed or grafted."""


# --------------------------------------------------------------------------
# PO strings


_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v", "\\": "\\", '"': '"', "'": "'", "?": "?"}
_ESCAPE_BACK = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r", "\a": "\\a", "\b": "\\b", "\f": "\\f", "\v": "\\v"}


def unescape(text: str) -> str:
    """Decode the C escapes of a PO string body (without its quotes)."""
    out: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char != "\\":
            out.append(char)
            i += 1
            continue
        if i + 1 >= len(text):
            raise PoError("string ends with a lone backslash")
        nxt = text[i + 1]
        if nxt in _ESCAPES:
            out.append(_ESCAPES[nxt])
            i += 2
        elif nxt in "01234567":
            match = re.match(r"[0-7]{1,3}", text[i + 1 :])
            out.append(chr(int(match.group(0), 8)))
            i += 1 + len(match.group(0))
        elif nxt == "x":
            match = re.match(r"[0-9a-fA-F]+", text[i + 2 :])
            if not match:
                raise PoError("\\x escape without hex digits")
            out.append(chr(int(match.group(0), 16)))
            i += 2 + len(match.group(0))
        else:
            raise PoError(f"unknown escape \\{nxt}")
    return "".join(out)


def escape(text: str) -> str:
    return "".join(_ESCAPE_BACK.get(char, char) for char in text)


def format_string(keyword: str, value: str, prefix: str = "") -> list[str]:
    """Format `keyword "value"` the way gettext does: one line when it fits,
    otherwise an empty first string and lines split after each newline and
    wrapped after spaces."""
    escaped = escape(value)
    single = f'{prefix}{keyword} "{escaped}"'
    inner_newline = "\\n" in escaped[:-2] if escaped.endswith("\\n") else "\\n" in escaped
    if len(single) <= WRAP_WIDTH and not inner_newline:
        return [single]
    lines = [f'{prefix}{keyword} ""']
    pieces = re.split(r"(?<=\\n)", escaped)
    limit = WRAP_WIDTH - len(prefix) - 2
    for piece in pieces:
        if not piece:
            continue
        current = ""
        for token in re.split(r"(?<= )", piece):
            if not token:
                continue
            if current and len(current) + len(token) > limit:
                lines.append(f'{prefix}"{current}"')
                current = ""
            current += token
        if current:
            lines.append(f'{prefix}"{current}"')
    return lines


# --------------------------------------------------------------------------
# PO entries and files


@dataclass
class Entry:
    """One catalogue entry. `raw` holds its original text (with the blank lines
    that follow it) until the entry is changed, so untouched entries are
    written back exactly."""

    comments: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    msgctxt: str | None = None
    msgid: str | None = None
    msgid_plural: str | None = None
    msgstr: str = ""
    msgstr_plural: dict[int, str] = field(default_factory=dict)
    obsolete: bool = False
    raw: str | None = None

    @property
    def key(self) -> tuple[str | None, str | None]:
        return (self.msgctxt, self.msgid)

    @property
    def is_header(self) -> bool:
        return self.msgctxt is None and self.msgid == "" and not self.obsolete

    @property
    def is_message(self) -> bool:
        """A real message: not a header, not obsolete, not a comment block."""
        return self.msgid is not None and not self.is_header and not self.obsolete

    @property
    def is_plural(self) -> bool:
        return self.msgid_plural is not None

    @property
    def fuzzy(self) -> bool:
        return "fuzzy" in self.flags

    @property
    def translated(self) -> bool:
        if self.is_plural:
            return bool(self.msgstr_plural) and all(self.msgstr_plural.values())
        return self.msgstr != ""

    def touch(self) -> None:
        self.raw = None

    def render(self) -> str:
        if self.raw is not None:
            return self.raw
        prefix = "#~ " if self.obsolete else ""
        lines = [c for c in self.comments if not c.startswith("#|")]
        if self.flags:
            lines.append("#, " + ", ".join(self.flags))
        lines.extend(c for c in self.comments if c.startswith("#|"))
        if self.msgid is not None:
            if self.msgctxt is not None:
                lines += format_string("msgctxt", self.msgctxt, prefix)
            lines += format_string("msgid", self.msgid, prefix)
            if self.is_plural:
                lines += format_string("msgid_plural", self.msgid_plural, prefix)
                for index in sorted(self.msgstr_plural):
                    lines += format_string(f"msgstr[{index}]", self.msgstr_plural[index], prefix)
            else:
                lines += format_string("msgstr", self.msgstr, prefix)
        return "\n".join(lines) + "\n\n"


@dataclass
class Catalogue:
    entries: list[Entry]
    path: Path | None = None
    # Line ending of the file it was read from; the text itself is held in LF.
    eol: str = "\n"

    @property
    def header(self) -> Entry | None:
        for entry in self.entries:
            if entry.is_header:
                return entry
        return None

    def messages(self) -> list[Entry]:
        return [entry for entry in self.entries if entry.is_message]

    def header_field(self, name: str) -> str | None:
        header = self.header
        if header is None:
            return None
        for line in header.msgstr.split("\n"):
            if line.lower().startswith(name.lower() + ":"):
                return line.split(":", 1)[1].strip()
        return None

    def render(self) -> str:
        text = "".join(entry.render() for entry in self.entries)
        # A file ends with exactly one newline, like gettext writes it.
        return text.rstrip("\n") + "\n" if text else ""


_KEYWORD = re.compile(r'^(msgctxt|msgid_plural|msgid|msgstr(?:\[(\d+)\])?)\s+"(.*)"\s*$')
_CONTINUATION = re.compile(r'^"(.*)"\s*$')


def parse_po(text: str, path: Path | None = None) -> Catalogue:
    """Parse a PO or POT file. Keeps each entry's original text."""
    where = str(path) if path else "<string>"
    if text.startswith("﻿"):
        raise PoError(f"{where}: byte order mark is not supported")
    lines = text.splitlines(keepends=True)
    entries: list[Entry] = []
    current: Entry | None = None
    raw_lines: list[str] = []
    last_keyword: str | None = None
    seen_msgstr = False

    def finish() -> None:
        nonlocal current, raw_lines, last_keyword, seen_msgstr
        if current is not None:
            if current.msgid is not None and not seen_msgstr:
                raise PoError(f"{where}: entry {current.msgid!r} has no msgstr")
            current.raw = "".join(raw_lines)
            entries.append(current)
        current, raw_lines, last_keyword, seen_msgstr = None, [], None, False

    def append_value(entry: Entry, keyword: str, value: str) -> None:
        if keyword == "msgctxt":
            entry.msgctxt = (entry.msgctxt or "") + value
        elif keyword == "msgid":
            entry.msgid = (entry.msgid or "") + value
        elif keyword == "msgid_plural":
            entry.msgid_plural = (entry.msgid_plural or "") + value
        elif keyword == "msgstr":
            entry.msgstr += value
        else:
            index = int(keyword[7:-1])
            entry.msgstr_plural[index] = entry.msgstr_plural.get(index, "") + value

    for number, line in enumerate(lines, start=1):
        stripped = line.rstrip("\r\n")
        if not stripped.strip():
            if current is None:
                # Blank lines before the first entry, or doubled blank lines,
                # stay with the previous entry so the text round-trips.
                if entries:
                    entries[-1].raw = (entries[-1].raw or "") + line
                else:
                    entries.append(Entry(raw=line))
                continue
            raw_lines.append(line)
            # Keep every following blank line in this entry's raw text.
            continue
        if current is not None and raw_lines and not raw_lines[-1].strip():
            finish()

        obsolete = stripped.startswith("#~")
        body = stripped
        if obsolete:
            body = stripped[2:].lstrip(" ")
            if body.startswith("|"):
                body = "#" + body

        match = _KEYWORD.match(body) if not body.startswith("#") else None
        if match and match.group(1) in ("msgctxt", "msgid") and current is not None and seen_msgstr:
            # A new entry starts without a blank line in between.
            finish()
        if body.startswith("#") and current is not None and seen_msgstr:
            finish()
        if current is None:
            current = Entry()
        raw_lines.append(line)
        if obsolete:
            current.obsolete = True

        if body.startswith("#,"):
            current.flags.extend(flag.strip() for flag in body[2:].split(",") if flag.strip())
            continue
        if body.startswith("#"):
            current.comments.append(body)
            continue
        if match:
            keyword = match.group(1)
            try:
                value = unescape(match.group(3))
            except PoError as error:
                raise PoError(f"{where}:{number}: {error}") from None
            if keyword == "msgid":
                current.msgid = ""
            if keyword.startswith("msgstr"):
                seen_msgstr = True
            append_value(current, keyword, value)
            last_keyword = keyword
            continue
        cont = _CONTINUATION.match(body)
        if cont and last_keyword is not None:
            try:
                append_value(current, last_keyword, unescape(cont.group(1)))
            except PoError as error:
                raise PoError(f"{where}:{number}: {error}") from None
            continue
        raise PoError(f"{where}:{number}: cannot parse line: {stripped!r}")
    finish()
    return Catalogue(entries=entries, path=path)


def line_ending(text: str) -> str:
    """The dominant line ending of `text`: CRLF when most lines end with it
    (a Windows checkout with core.autocrlf), LF otherwise."""
    crlf = text.count("\r\n")
    return "\r\n" if crlf > text.count("\n") - crlf else "\n"


def read_po(path: Path) -> Catalogue:
    """Parse a catalogue file of either line ending. The catalogue holds LF
    text and remembers the file's line ending in `eol`."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    eol = line_ending(text)
    catalogue = parse_po(text.replace("\r\n", "\n"), path)
    catalogue.eol = eol
    return catalogue


def write_text(path: Path, text: str, eol: str = "\n") -> None:
    """Write UTF-8 text with one line ending throughout: LF by default, or the
    `eol` of the file it was read from, so a CRLF checkout stays CRLF."""
    text = text.replace("\r\n", "\n")
    with path.open("w", encoding="utf-8", newline=eol) as handle:
        handle.write(text)


# --------------------------------------------------------------------------
# Graft


@dataclass
class CosmyxEntry:
    feature: str
    path: Path
    entry: Entry


@dataclass
class LanguageResult:
    language: str
    replaced: int = 0
    appended: int = 0
    appended_untranslated: int = 0
    kept_orca: int = 0
    dropped_obsolete: int = 0
    catalogue: Catalogue | None = None
    target: Path | None = None

    @property
    def changed(self) -> bool:
        return bool(self.replaced or self.appended or self.appended_untranslated or self.dropped_obsolete)


@dataclass
class GraftReport:
    results: list[LanguageResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def orca_languages(i18n_dir: Path) -> dict[str, Path]:
    """Map each language OrcaSlicer ships to its OrcaSlicer_<lang>.po."""
    languages = {}
    for folder in sorted(p for p in i18n_dir.iterdir() if p.is_dir()):
        po = folder / f"OrcaSlicer_{folder.name}.po"
        if po.is_file():
            languages[folder.name] = po
    return languages


def cosmyx_catalogues(cosmyx_dir: Path) -> dict[str, list[tuple[str, Path]]]:
    """Map each language to its (feature, <lang>.po) files."""
    by_language: dict[str, list[tuple[str, Path]]] = {}
    if not cosmyx_dir.is_dir():
        return by_language
    for feature_dir in sorted(p for p in cosmyx_dir.iterdir() if p.is_dir()):
        for po in sorted(feature_dir.glob("*.po")):
            by_language.setdefault(po.stem, []).append((feature_dir.name, po))
    return by_language


def collect_language(files: list[tuple[str, Path]]) -> dict[tuple, CosmyxEntry]:
    """Read one language's Cosmyx entries, refusing duplicate keys."""
    entries: dict[tuple, CosmyxEntry] = {}
    for feature, path in files:
        for entry in read_po(path).messages():
            other = entries.get(entry.key)
            if other is not None:
                place = "twice in" if other.path == path else f"in both {other.path} and"
                raise PoError(f"msgid {entry.msgid!r} (msgctxt {entry.msgctxt!r}) is defined {place} {path}")
            entries[entry.key] = CosmyxEntry(feature, path, entry)
    return entries


def graft_language(language: str, orca: Catalogue, cosmyx: dict[tuple, CosmyxEntry]) -> LanguageResult:
    """Merge Cosmyx entries into an OrcaSlicer catalogue, in memory."""
    result = LanguageResult(language=language, catalogue=orca)
    active = {entry.key: entry for entry in orca.entries if entry.is_message}
    obsolete_keys = {entry.key for entry in orca.entries if entry.obsolete and entry.msgid is not None}
    dropped: set[tuple] = set()

    for key, item in cosmyx.items():
        source = item.entry
        target = active.get(key)
        if target is not None:
            if target.is_plural != source.is_plural:
                raise PoError(f"{item.path}: msgid {source.msgid!r} is {'plural' if source.is_plural else 'singular'} in Cosmyx but not in OrcaSlicer_{language}.po")
            if source.translated and not source.fuzzy:
                target.msgstr = source.msgstr
                target.msgstr_plural = dict(source.msgstr_plural)
                target.flags = [flag for flag in target.flags if flag != "fuzzy"]
                target.comments = [c for c in target.comments if not c.startswith("#|")]
                target.touch()
                result.replaced += 1
            else:
                result.kept_orca += 1
            continue
        if key in obsolete_keys:
            dropped.add(key)
        appended = copy.deepcopy(source)
        appended.touch()
        orca.entries.append(appended)
        if source.translated and not source.fuzzy:
            result.appended += 1
        else:
            result.appended_untranslated += 1

    if dropped:
        before = len(orca.entries)
        orca.entries = [e for e in orca.entries if not (e.obsolete and e.key in dropped)]
        result.dropped_obsolete = before - len(orca.entries)
    return result


def graft(i18n_dir: Path, cosmyx_dir: Path) -> GraftReport:
    """Compute the graft of every language. Writes nothing."""
    report = GraftReport()
    orca = orca_languages(i18n_dir)
    for language, files in sorted(cosmyx_catalogues(cosmyx_dir).items()):
        entries = collect_language(files)
        if language not in orca:
            features = ", ".join(sorted({feature for feature, _ in files}))
            report.warnings.append(f"language {language!r} ({features}) has no OrcaSlicer catalogue in {i18n_dir}; skipped")
            continue
        catalogue = read_po(orca[language])
        orca_plural = catalogue.header_field("Plural-Forms")
        for feature, path in files:
            plural = read_po(path).header_field("Plural-Forms")
            if plural is not None and orca_plural is not None and plural != orca_plural:
                report.warnings.append(f"{path}: Plural-Forms differs from OrcaSlicer_{language}.po")
        result = graft_language(language, catalogue, entries)
        result.target = orca[language]
        report.results.append(result)
    return report


def summary_markdown(report: GraftReport, dry_run: bool) -> str:
    title = "Cosmyx translations graft" + (" (dry run)" if dry_run else "")
    lines = [f"### {title}", "", "| Language | Replaced | Appended | Appended untranslated | Kept OrcaSlicer | Dropped obsolete |", "|---|---|---|---|---|---|"]
    for r in report.results:
        lines.append(f"| {r.language} | {r.replaced} | {r.appended} | {r.appended_untranslated} | {r.kept_orca} | {r.dropped_obsolete} |")
    if not report.results:
        lines.append("| (none) | 0 | 0 | 0 | 0 | 0 |")
    for warning in report.warnings:
        lines.append("")
        lines.append(f"- Warning: {warning}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--i18n-dir", type=Path, default=DEFAULT_I18N_DIR, help="OrcaSlicer catalogues (default: localization/i18n)")
    parser.add_argument("--cosmyx-dir", type=Path, default=DEFAULT_COSMYX_DIR, help="Cosmyx catalogues (default: localization/cosmyx)")
    parser.add_argument("--dry-run", action="store_true", help="check and count, write nothing")
    parser.add_argument("--summary", type=Path, default=None, help="append a Markdown summary here (default: $GITHUB_STEP_SUMMARY when set)")
    args = parser.parse_args(argv)

    in_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    try:
        report = graft(args.i18n_dir, args.cosmyx_dir)
    except (PoError, OSError) as error:
        print(f"{'::error title=Cosmyx graft::' if in_actions else 'error: '}{error}", file=sys.stderr)
        return 1

    for warning in report.warnings:
        print(f"{'::warning title=Cosmyx graft::' if in_actions else 'warning: '}{warning}", file=sys.stderr)
    for result in report.results:
        if not args.dry_run and result.changed:
            write_text(result.target, result.catalogue.render(), result.catalogue.eol)
        print(
            f"{result.language}: {result.replaced} replaced, {result.appended} appended, "
            f"{result.appended_untranslated} appended untranslated, {result.kept_orca} kept OrcaSlicer, "
            f"{result.dropped_obsolete} dropped obsolete"
        )
    if args.dry_run:
        print("Dry run: nothing written.")
    else:
        print("Grafted in place. Run `just i18n-ungraft` before committing.")

    summary = args.summary or (Path(os.environ["GITHUB_STEP_SUMMARY"]) if os.environ.get("GITHUB_STEP_SUMMARY") else None)
    if summary is not None:
        with summary.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(summary_markdown(report, args.dry_run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
