"""Readers (and the hint rename) for the resources that show the product name.

- `resources/data/hints.ini`: the hint texts are msgids too (the template
  extracts them), so a hint is renamed together with its msgid.
- `resources/web/guide/**/*.html`: the fallback text of the elements the setup
  guide translates (`data-i18n` or class `trans`), shown until the page gets
  its strings. These are fixed by patch rows; the reader only finds residue.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from .. import relative_posix, repo_path
from .tokens import replace_tokens

HINTS_FILE = "resources/data/hints.ini"
GUIDE_DIR = "resources/web/guide"

_SECTION = re.compile(r"^\s*\[(?P<name>[^\]]+)\]\s*$")
_TEXT = re.compile(r"^(?P<lead>\s*text\s*=\s*)(?P<value>.*?)(?P<trail>\s*)$")
_HINT_ESCAPES = {"n": "\n", '"': '"', "\\": "\\", "t": "\t"}
_HINT_ENCODE = {"\\": "\\\\", "\n": "\\n", '"': '\\"', "\t": "\\t"}


def decode_hint(raw: str) -> str:
    out = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw) and raw[i + 1] in _HINT_ESCAPES:
            out.append(_HINT_ESCAPES[raw[i + 1]])
            i += 2
        else:
            out.append(raw[i])
            i += 1
    return "".join(out)


def encode_hint(value: str) -> str:
    return "".join(_HINT_ENCODE.get(char, char) for char in value)


def hint_lines(text: str) -> list[tuple[int, str, str]]:
    """(line index, section, raw value) of every `text = ...` line."""
    found = []
    section = ""
    for index, line in enumerate(text.split("\n")):
        header = _SECTION.match(line)
        if header:
            section = header.group("name")
            continue
        if line.lstrip().startswith(("#", ";")):
            continue
        match = _TEXT.match(line)
        if match and section:
            found.append((index, section, match.group("value")))
    return found


def hint_texts(root: Path) -> dict:
    """{section: decoded text}."""
    path = repo_path(root, HINTS_FILE)
    if not path.is_file():
        return {}
    text = path.read_bytes().decode("utf-8")
    return {section: decode_hint(raw) for _, section, raw in hint_lines(text)}


def rename_hints(text: str, mapping: dict) -> tuple[str, dict]:
    """`text` with every hint whose decoded value is a key of `mapping` renamed."""
    lines = text.split("\n")
    counts: dict = {}
    for index, _, raw in hint_lines(text):
        old = decode_hint(raw)
        new = mapping.get(old)
        if new is None:
            continue
        counts[old] = counts.get(old, 0) + 1
        body = replace_tokens(raw)
        if decode_hint(body) != new:
            body = encode_hint(new)
        match = _TEXT.match(lines[index])
        lines[index] = match.group("lead") + body + match.group("trail")
    return "\n".join(lines), counts


class _GuideParser(HTMLParser):
    """Text of the elements a guide page translates (`data-i18n` or class `trans`)."""

    VOID = {"br", "img", "input", "meta", "link", "hr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[bool] = []
        self.texts: list[tuple[int, str]] = []

    def handle_starttag(self, tag, attrs) -> None:
        if tag in self.VOID:
            return
        values = dict(attrs)
        own = "data-i18n" in values or "trans" in (values.get("class") or "").split()
        self.stack.append(own or (bool(self.stack) and self.stack[-1]))

    def handle_endtag(self, tag) -> None:
        if tag not in self.VOID and self.stack:
            self.stack.pop()

    def handle_data(self, data) -> None:
        if self.stack and self.stack[-1] and data.strip():
            self.texts.append((self.getpos()[0], " ".join(data.split())))


def guide_texts(root: Path) -> list[tuple[str, int, str]]:
    """(path, line, text) of every translated element of every guide page."""
    base = repo_path(root, GUIDE_DIR)
    if not base.is_dir():
        return []
    found = []
    for page in sorted(base.rglob("*.html"), key=lambda path: path.as_posix()):
        parser = _GuideParser()
        parser.feed(page.read_bytes().decode("utf-8"))
        relative = relative_posix(root, page)
        found += [(relative, line, text) for line, text in parser.texts]
    return found
