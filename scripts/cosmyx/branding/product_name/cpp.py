"""A small C++ lexer for string literals, and the build-time literal rename.

`literals` returns every string literal of a source with its offsets, line,
prefix and statement context. Comments, character literals, digit separators
(`1'000`), escaped quotes and raw strings (`R"d(...)d"`) are handled.

`groups` joins adjacent literals (`"a" "b"`, separated only by whitespace or
comments) the way the compiler concatenates them, and decodes their value.
`rename` rewrites every group whose value is an old text of the rename table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .tokens import replace_tokens

LOG_MARKERS = ("BOOST_LOG_TRIVIAL", "COSMYX_LOG", "COSMO_LOG")

_LEXER = re.compile(
    r"""
    (?P<line_comment>//[^\n]*)
    |(?P<block_comment>/\*.*?(?:\*/|\Z))
    |(?P<raw>(?<![0-9A-Za-z_])(?P<raw_prefix>u8|[uUL])?R"(?P<delim>[^()\\\s]{0,16})\((?P<raw_body>.*?)\)(?P=delim)")
    |(?P<string>(?:(?<![0-9A-Za-z_])(?P<prefix>u8|[uUL]))?"(?P<body>(?:[^"\\\n]|\\.)*)")
    |(?P<number>(?<![0-9A-Za-z_])[0-9][0-9A-Za-z_'.]*)
    |(?P<char>'(?:[^'\\\n]|\\.)*')
    |(?P<directive>^[ \t]*\#)
    |(?P<newline>\n)
    |(?P<punct>[;{}])
    """,
    re.S | re.M | re.X,
)
_BETWEEN = re.compile(r"(?:\s|//[^\n]*|/\*.*?\*/)*", re.S)
_SIMPLE_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "a": "\a", "b": "\b", "f": "\f", "v": "\v", "\\": "\\", '"': '"', "'": "'", "?": "?"}
_ENCODE = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t", "\r": "\\r"}


@dataclass(frozen=True)
class Literal:
    """One string literal. `raw` is the source text between the quotes."""

    path: str
    line: int
    prefix: str
    raw: str
    context: str
    start: int
    end: int
    body_start: int
    body_end: int
    is_raw: bool

    @property
    def is_log(self) -> bool:
        return any(marker in self.context for marker in LOG_MARKERS)

    @property
    def is_include(self) -> bool:
        return re.match(r"\s*#\s*(?:include|import)\b", self.context) is not None

    @property
    def value(self) -> str:
        return self.raw if self.is_raw else decode(self.raw)


def decode(raw: str) -> str:
    """The value of a C++ (non-raw) literal body. Unknown escapes keep their character."""
    out = []
    i = 0
    while i < len(raw):
        char = raw[i]
        if char != "\\" or i + 1 >= len(raw):
            out.append(char)
            i += 1
            continue
        nxt = raw[i + 1]
        if nxt in _SIMPLE_ESCAPES:
            out.append(_SIMPLE_ESCAPES[nxt])
            i += 2
        elif nxt in "01234567":
            digits = re.match(r"[0-7]{1,3}", raw[i + 1 :]).group(0)
            out.append(chr(int(digits, 8)))
            i += 1 + len(digits)
        elif nxt in "xuU":
            size = {"x": None, "u": 4, "U": 8}[nxt]
            match = re.match(r"[0-9A-Fa-f]+" if size is None else f"[0-9A-Fa-f]{{{size}}}", raw[i + 2 :])
            if not match:
                out.append(nxt)
                i += 2
                continue
            out.append(chr(int(match.group(0), 16)))
            i += 2 + len(match.group(0))
        else:
            out.append(nxt)
            i += 2
    return "".join(out)


def encode(value: str) -> str:
    """A literal body whose value is `value` (UTF-8 source, so other characters stay)."""
    return "".join(_ENCODE.get(char, char) for char in value)


def literals(source: str, path: str = "") -> list[Literal]:
    """Every string literal of `source`, in order."""
    found: list[Literal] = []
    line = 1
    statement_start = 0
    directive_start = None
    for match in _LEXER.finditer(source):
        kind = match.lastgroup
        if kind == "newline":
            line += 1
            if directive_start is not None and source[max(0, match.start() - 1)] != "\\":
                directive_start = None
                statement_start = match.end()
            continue
        if kind == "directive":
            directive_start = match.start()
            continue
        if kind == "punct":
            if directive_start is None:
                statement_start = match.end()
            continue
        if kind in ("raw", "string"):
            is_raw = kind == "raw"
            body = "raw_body" if is_raw else "body"
            prefix = (match.group("raw_prefix") or "") + "R" if is_raw else match.group("prefix") or ""
            context_start = directive_start if directive_start is not None else statement_start
            found.append(
                Literal(
                    path,
                    line,
                    prefix,
                    match.group(body),
                    source[context_start : match.start()],
                    match.start(),
                    match.end(),
                    match.start(body),
                    match.end(body),
                    is_raw,
                )
            )
        line += source.count("\n", match.start(), match.end())
    return found


@dataclass(frozen=True)
class Group:
    """Adjacent literals the compiler concatenates into one string."""

    pieces: tuple

    @property
    def value(self) -> str:
        return "".join(piece.value for piece in self.pieces)

    @property
    def start(self) -> int:
        return self.pieces[0].start

    @property
    def end(self) -> int:
        return self.pieces[-1].end

    @property
    def is_log(self) -> bool:
        return any(piece.is_log for piece in self.pieces)


def groups(source: str, path: str = "", found: list | None = None) -> list[Group]:
    found = literals(source, path) if found is None else found
    result: list[list[Literal]] = []
    for literal in found:
        if result and _BETWEEN.fullmatch(source, result[-1][-1].end, literal.start):
            result[-1].append(literal)
        else:
            result.append([literal])
    return [Group(tuple(pieces)) for pieces in result]


def rewrite_group(group: Group, new: str) -> list[tuple[int, int, str]]:
    """Edits (start, end, text) turning `group` into a string whose value is `new`.

    The upstream name is replaced inside each piece when that gives `new`
    (the layout stays as it was); otherwise the group becomes one literal.
    """
    edits = []
    pieces = []
    for piece in group.pieces:
        body = replace_tokens(piece.raw)
        pieces.append(body if piece.is_raw else decode(body))
        if body != piece.raw:
            edits.append((piece.body_start, piece.body_end, body))
    if "".join(pieces) == new:
        return edits
    prefix = group.pieces[0].prefix.replace("R", "")
    return [(group.start, group.end, f'{prefix}"{encode(new)}"')]


def rename(source: str, mapping: dict, path: str = "") -> tuple[str, dict]:
    """`source` with every literal group whose value is a key of `mapping`
    rewritten to its value, and {old: number of groups renamed}."""
    edits = []
    counts: dict = {}
    for group in groups(source, path):
        new = mapping.get(group.value)
        if new is None:
            continue
        counts[group.value] = counts.get(group.value, 0) + 1
        edits += rewrite_group(group, new)
    for start, end, text in sorted(edits, reverse=True):
        source = source[:start] + text + source[end:]
    return source, counts
