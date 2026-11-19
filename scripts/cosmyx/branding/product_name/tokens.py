"""The upstream product name as a token, and its replacement by CosmoSlice.

- `TOKEN` finds the upstream name as a word: OrcaSlicer, Orca Slicer,
  Orcaslicer, Orca, ORCA, and the "Orc slicer" misspelling some translations
  carry. It may follow an escaped newline (`\\nOrca` in C++ or PO source).
  Identifiers never match: lowercase ones (`orca_slicer`, `orcaslicer.com`)
  and the ones the name runs into (`OrcaSlicerVersion`, `ORCA_CAD_GLYPH`,
  `OrcaSlicer_192px`).
- `NATIVE_TOKENS` are the spellings some translations use for the name.
- `replace_tokens` rewrites the name to CosmoSlice outside URLs, file names
  and the kept names (`KEPT_NAMES`: things upstream calls that, such as the
  Orca Cloud service or the Orca Cube model), so a link to the upstream wiki,
  an icon name or a built-in model keeps working.
- `visible_name` is the residue test: the text still names the upstream
  product somewhere `replace_tokens` would rewrite.
"""

from __future__ import annotations

import re

NEW_NAME = "CosmoSlice"

TOKEN = re.compile(r"(?:(?<![A-Za-z0-9_])|(?<=\\n))(?:Orca ?[Ss]licer|Orc ?[Ss]licer|Orca|ORCA)(?![A-Za-z0-9_])")

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
    r"|[\w-]+/[\w./-]*[Oo]rca[\w./-]*"  # paths such as orca/OrcaCube_v2.3mf
    # Paths such as OrcaSlicer/build: a slash, a doubled (C source) backslash,
    # or a backslash that does not start an escape sequence.
    r"|[\w.-]*[Oo]rca[\w.-]*(?:/|\\\\|\\(?![abfnrtv\"'?\\0-7xuU]))[\w./\\-]*"
    r"|[A-Za-z][\w-]*(?:\.[\w-]+){2,}"  # dotted ids such as com.orcaslicer.OrcaSlicer
    r"|//\s*(?:ORCA|Orca)\b"  # source comment markers inside embedded code
)


def has_token(text: str) -> bool:
    return TOKEN.search(text) is not None


def has_native_token(text: str, language: str | None) -> bool:
    pattern = NATIVE_TOKENS.get(language or "")
    return bool(pattern and pattern.search(text))


def names_product(text: str, language: str | None = None) -> bool:
    """True when `text` names the upstream product, in English or natively."""
    return has_token(text) or has_native_token(text, language)


def visible_name(text: str, language: str | None = None) -> bool:
    """True when `text` names the upstream product where it would be renamed."""
    return replace_tokens(text, language) != text


def protected_spans(text: str) -> list[tuple[int, int]]:
    return [match.span() for match in _PROTECTED.finditer(text)]


def replace_tokens(text: str, language: str | None = None, new: str = NEW_NAME) -> str:
    """`text` with every upstream name outside URLs and file names replaced by `new`."""
    spans = protected_spans(text)

    def inside(start: int, end: int) -> bool:
        return any(low <= start and end <= high for low, high in spans)

    patterns = [TOKEN]
    native = NATIVE_TOKENS.get(language or "")
    if native is not None:
        patterns.append(native)
    for pattern in patterns:
        pieces = []
        last = 0
        for match in pattern.finditer(text):
            if inside(*match.span()):
                continue
            pieces.append(text[last : match.start()])
            pieces.append(new)
            last = match.end()
        pieces.append(text[last:])
        text = "".join(pieces)
        spans = protected_spans(text)
    return text
