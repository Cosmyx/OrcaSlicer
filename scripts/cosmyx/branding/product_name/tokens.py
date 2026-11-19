"""The upstream product name as a token, and its replacement by CosmoSlice.

- `TOKEN` finds the upstream name as a word: OrcaSlicer, Orca Slicer,
  Orcaslicer, ORCA SLICER, ORCASLICER, Orca, ORCA, and the "Orc slicer"
  misspelling some translations carry. It may follow an escaped newline
  (`\\nOrca` in C++ or PO source). Identifiers never match: lowercase ones
  (`orca_slicer`, `orcaslicer.com`) and the ones the name runs into
  (`OrcaSlicerVersion`, `ORCA_CAD_GLYPH`, `OrcaSlicer_192px`). A combining
  mark after the name makes another word ("Orca" + U+0301), never a match.
- An inflected name is the name glued to a lowercase Latin suffix, as
  inflected languages write it (cs "OrcaSliceru", hu "OrcaSlicerrel", eu
  "OrcaSlicerren"). It is a name only in a translation (a language is
  given): in English text "Orcas" is another word. Only a per-language row of the `inflections` table can
  rename it: the suffix depends on the new name, so it is never guessed.
  Without a row the name stays and `unresolved` reports it.
- `NATIVE_TOKENS` are the spellings some translations use for the name.
- `replace_tokens` rewrites the name to CosmoSlice outside URLs, file names,
  the names tied to the app key (`OrcaSlicer.conf`, `.app`, `.AppImage`, the
  Windows data folder `...\\OrcaSlicer`, decision 0133) and the kept names
  (`KEPT_NAMES`: things upstream calls that, such as the Orca Cloud service
  or the Orca Cube model), so a link to the upstream wiki, an icon name, a
  real file or a built-in model keeps working. With a language, the
  inflection rows of that language are applied first.
- `visible_name` is the residue test: the text still names the upstream
  product somewhere `replace_tokens` would rewrite, or where only a missing
  inflection row keeps it.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

NEW_NAME = "CosmoSlice"

# Combining marks: a name followed by one is another word ("Orca" + U+0301).
_COMBINING = "\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f"
# Lowercase Latin letters (accented ones included) an inflection glues to the name.
_SUFFIX = "a-z\u00df-\u00f6\u00f8-\u00ff\u0100-\u024f"

TOKEN = re.compile(
    r"(?:(?<![A-Za-z0-9_])|(?<=\\n))"
    r"(?:Orca ?[Ss]licer|ORCA ?SLICER|Orc ?[Ss]licer|Orca|ORCA)"
    rf"(?P<suffix>[{_SUFFIX}]*)"
    rf"(?![A-Za-z0-9_{_COMBINING}])"
)

# The committed inflection table, used when a caller passes none.
INFLECTIONS_FILE = Path(__file__).resolve().parents[4] / "cosmyx-src" / "branding" / "product-name" / "inflections.json"

# Native spellings, per catalogue language. Longest first: the Korean
# "Orca Slicer" goes as a whole before the bare "Orca".
NATIVE_TOKENS = {
    "zh_CN": re.compile("逆戟[鲸鯨]"),
    "zh_TW": re.compile("逆戟[鯨鲸]"),
    "ko": re.compile("오르카 ?슬라이서|오르카"),
}

# Names that keep "Orca" on purpose: they name an upstream service, a built-in
# model or calibration, or a file format, not this application (decision 0134).
KEPT_NAMES = (
    r"Orca ?Cloud",
    r"Orca Cube",
    r"Orca String Hell",
    r"Orca Tolerance Test",
    r"Orca YOLO",
    r"Orca Arena",
    r"Orca Palette",
    r"Orca Badge",
    r"OrcaSliced Combo",
    r"Orca Preset Bundle",
    r"Orca Filament Library",
    r"OrcaFilamentLibrary",
)

# Spans where the name is part of an address, a file name or a kept name.
_PROTECTED = re.compile(
    r"(?:" + "|".join(KEPT_NAMES) + r")(?![a-z])|"
    r"(?:[a-z][a-z0-9+.-]*://|www\.)[^\s\"'<>)\]]*"  # URLs
    r"|[\w.%-]*[Oo]rca[\w%-]*\.(?:png|svg|ico|icns|3mf|stl|step|dll|exe|desktop|json|html|js|css)\b"  # file names
    r"|[\w.%-]*[Oo]rca[\w%-]*\.(?:conf|app|AppImage)\b"  # names derived from the app key (decision 0133)
    r"|[\w-]+/[\w./-]*[Oo]rca[\w./-]*"  # paths such as orca/OrcaCube_v2.3mf
    # Paths such as OrcaSlicer/build: a slash, a doubled (C source) backslash,
    # or a backslash that does not start an escape sequence.
    r"|[\w.-]*[Oo]rca[\w.-]*(?:/|\\\\|\\(?![abfnrtv\"'?\\0-7xuU]))[\w./\\-]*"
    # Windows folders such as %APPDATA%\OrcaSlicer: the name after a backslash
    # that does not start an escape sequence (or a doubled one).
    r"|[\w.%:-]*(?:\\\\|\\(?![abfnrtv\"'?\\0-7xuU]))[\w.%-]*[Oo]rca[\w.-]*"
    r"|[A-Za-z][\w-]*(?:\.[\w-]+){2,}"  # dotted ids such as com.orcaslicer.OrcaSlicer
    r"|//\s*(?:ORCA|Orca)\b"  # source comment markers inside embedded code
)


def has_token(text: str) -> bool:
    """True when `text` names the upstream product as an English word (no inflection)."""
    return any(not match.group("suffix") for match in TOKEN.finditer(text))


def has_native_token(text: str, language: str | None) -> bool:
    pattern = NATIVE_TOKENS.get(language or "")
    return bool(pattern and pattern.search(text))


def names_product(text: str, language: str | None = None) -> bool:
    """True when `text` names the upstream product, in English or natively."""
    return has_token(text) or has_native_token(text, language)


def is_inflected(form: str) -> bool:
    """True when `form` is exactly one inflected upstream name ("OrcaSliceru")."""
    match = TOKEN.fullmatch(form)
    return bool(match and match.group("suffix"))


# ---------------------------------------------------------------- inflections

_default_rows: dict | None = None


def inflection_map(rows: list) -> dict:
    """{language: [(old, new), ...] longest old first} from validated rows."""
    by_language: dict = {}
    for row in rows:
        by_language.setdefault(row["language"], []).append((row["old"], row["new"]))
    return {language: sorted(pairs, key=lambda pair: (-len(pair[0]), pair[0])) for language, pairs in by_language.items()}


def default_inflections() -> dict:
    """The committed inflection rows (none when the table is absent)."""
    global _default_rows
    if _default_rows is None:
        from .tables import inflection_rows  # local import: tables imports this module

        rows = []
        if INFLECTIONS_FILE.is_file():
            rows = json.loads(INFLECTIONS_FILE.read_text(encoding="utf-8")).get("rows", [])
        _default_rows = inflection_map(inflection_rows(rows))
    return _default_rows


# ---------------------------------------------------------------- rename


def protected_spans(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in _PROTECTED.finditer(text)]


def _inside(spans: list, start: int, end: int) -> bool:
    return any(low <= start and end <= high for low, high in spans)


def _rewrite(text: str, language: str | None, new: str, inflections: dict | None) -> tuple[str, list[str]]:
    """(renamed text, inflected forms left because no row renames them)."""
    pairs = (default_inflections() if inflections is None else inflections).get(language or "", [])
    for old, replacement in pairs:
        spans = protected_spans(text)
        pieces, last, start = [], 0, text.find(old)
        while start >= 0:
            end = start + len(old)
            if not _inside(spans, start, end):
                pieces += [text[last:start], replacement]
                last = end
            start = text.find(old, end)
        text = "".join(pieces) + text[last:]

    unresolved: list[str] = []
    spans = protected_spans(text)
    pieces, last = [], 0
    for match in TOKEN.finditer(text):
        if _inside(spans, *match.span()):
            continue
        if match.group("suffix"):
            # An inflection only exists in a translation; in English it is another word.
            if language is not None:
                unresolved.append(match.group(0))
            continue
        pieces += [text[last : match.start()], new]
        last = match.end()
    text = "".join(pieces) + text[last:]

    native = NATIVE_TOKENS.get(language or "")
    if native is not None:
        spans = protected_spans(text)
        pieces, last = [], 0
        for match in native.finditer(text):
            if _inside(spans, *match.span()):
                continue
            pieces += [text[last : match.start()], new]
            last = match.end()
        text = "".join(pieces) + text[last:]
    return text, unresolved


def replace_tokens(text: str, language: str | None = None, new: str = NEW_NAME, inflections: dict | None = None) -> str:
    """`text` with every upstream name outside URLs and file names replaced by `new`.

    `inflections` is an `inflection_map`; None uses the committed table. An
    inflected name without a row for `language` is left as it is.
    """
    return _rewrite(text, language, new, inflections)[0]


def unresolved(text: str, language: str | None = None, inflections: dict | None = None) -> list[str]:
    """The inflected upstream names of `text` that no inflection row of `language` renames."""
    return _rewrite(text, language, NEW_NAME, inflections)[1]


def visible_name(text: str, language: str | None = None, inflections: dict | None = None) -> bool:
    """True when `text` names the upstream product where it would be renamed,
    or in an inflected form that still needs its inflection row."""
    renamed, left = _rewrite(text, language, NEW_NAME, inflections)
    return renamed != text or bool(left)
