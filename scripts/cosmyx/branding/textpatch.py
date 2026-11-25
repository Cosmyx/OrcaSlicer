"""Exact, counted, all-or-nothing text replacements.

A patch row is `{"file", "old", "new", "count", "reason"}`: `old` must occur
exactly `count` times in `file` (a repository-relative path), and every
occurrence becomes `new`. The colour literal rows of colours.json use the same
shape with `find` / `replace` keys; `normalise` maps them.

`plan` checks every row and computes every new file content in memory;
nothing is written unless every row matches, so a failed patch leaves the
tree as it was. Patched files must be UTF-8. Matching is done on LF text
and a patched file is written back with its own dominant line ending, so a
CRLF checkout (Windows, core.autocrlf) patches exactly like an LF one.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import BrandingError, check_relative, decode_text, encode_text, tree_path

KEYS = ("file", "old", "new", "count", "reason")


@dataclass(frozen=True)
class Patch:
    file: str
    old: str
    new: str
    count: int
    reason: str


def normalise(row: dict) -> Patch:
    """A Patch from a row, accepting `find` / `replace` for `old` / `new`."""
    if not isinstance(row, dict):
        raise BrandingError(f"patch row is not an object: {row!r}")
    data = dict(row)
    if "find" in data or "replace" in data:
        data["old"] = data.pop("find", None)
        data["new"] = data.pop("replace", None)
    missing = [key for key in KEYS if key not in data]
    if missing:
        raise BrandingError(f"patch row {row!r} lacks {', '.join(missing)}")
    if not isinstance(data["old"], str) or not data["old"]:
        raise BrandingError(f"patch row {row!r}: old/find must be a non-empty string")
    if not isinstance(data["new"], str):
        raise BrandingError(f"patch row {row!r}: new/replace must be a string")
    count = data["count"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 1:
        raise BrandingError(f"patch row {row!r}: count must be a positive integer")
    if not isinstance(data["reason"], str) or not data["reason"].strip():
        raise BrandingError(f"patch row {row!r}: reason must be given")
    return Patch(check_relative(data["file"]), data["old"], data["new"], count, data["reason"])


def read_text_eol(root: Path, relative: str) -> tuple[str, str]:
    """(LF text, the file's line ending). The path must be a file of the tree
    under its exact spelling (see `tree_path`)."""
    path = tree_path(root, relative)
    try:
        data = path.read_bytes()
    except OSError as error:
        raise BrandingError(f"{relative}: cannot read: {error}") from error
    try:
        return decode_text(data)
    except UnicodeDecodeError as error:
        raise BrandingError(f"{relative}: not UTF-8: {error}") from error


def read_text(root: Path, relative: str) -> str:
    """The file's text with LF line endings."""
    return read_text_eol(root, relative)[0]


def mismatches(root: Path, patches: list[Patch]) -> list[str]:
    """Every row whose `old` does not occur exactly `count` times, as messages.

    Rows on the same file are checked in order, each on the text left by the
    rows before it, as `plan` applies them.
    """
    problems = []
    texts: dict = {}
    for patch in patches:
        if patch.file not in texts:
            try:
                texts[patch.file] = read_text(root, patch.file)
            except BrandingError as error:
                problems.append(str(error))
                texts[patch.file] = None
        text = texts[patch.file]
        if text is None:
            continue
        found = text.count(patch.old)
        if found != patch.count:
            problems.append(f"{patch.file}: {patch.old!r} found {found} time(s), expected {patch.count} ({patch.reason})")
            continue
        texts[patch.file] = text.replace(patch.old, patch.new)
    return problems


def split_absent(root: Path, patches: list[Patch]) -> tuple[list[Patch], list[tuple[Patch, str]]]:
    """(rows to apply, [(row, why)] for the rows whose file or `old` text the
    tree lacks entirely). Used in tolerant mode only, on a tree older than
    the tables. A row whose text is there with another count is kept, so
    `mismatches` still reports it. Rows on the same file are checked in
    order on the text left by the kept rows before it."""
    kept, absent = [], []
    texts: dict = {}
    for patch in patches:
        if patch.file not in texts:
            # tree_path still refuses an unsafe path or a case-only spelling.
            texts[patch.file] = read_text(root, patch.file) if tree_path(root, patch.file).is_file() else None
        text = texts[patch.file]
        if text is None:
            absent.append((patch, "file is absent"))
        elif patch.old not in text:
            absent.append((patch, f"text {patch.old[:60]!r} is absent"))
        else:
            kept.append(patch)
            texts[patch.file] = text.replace(patch.old, patch.new)
    return kept, absent


def plan(root: Path, patches: list[Patch]) -> dict:
    """{relative path: new text} for every patched file; raises on any mismatch."""
    problems = mismatches(root, patches)
    if problems:
        raise BrandingError("text patch refused:\n  " + "\n  ".join(problems))
    texts: dict = {}
    for patch in patches:
        text = texts.get(patch.file)
        if text is None:
            text = read_text(root, patch.file)
        texts[patch.file] = text.replace(patch.old, patch.new)
    return texts


def apply(root: Path, patches: list[Patch], before_write=None) -> list[str]:
    """Apply every row or none. `before_write(path)` runs before each write
    (the pipeline backs the file up there). Returns the patched paths."""
    texts = plan(root, patches)
    for relative in sorted(texts):
        if before_write is not None:
            before_write(relative)
        _, eol = read_text_eol(root, relative)
        tree_path(root, relative).write_bytes(encode_text(texts[relative], eol))
    return sorted(texts)
