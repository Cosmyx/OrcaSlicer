"""The product-name tables: `rename` and `allowlist` rows, validated.

rename row: `{"kind": "msgid" | "literal", "old", "new", "source"}`

- `msgid`: a translatable text. Its C++ literal(s) (or its hint) and its
  msgid in every catalogue are renamed together.
- `literal`: a visible text that is not translated (no msgid).
- `source`: where the row comes from (`cosmoslice` for the frozen CosmoSlice
  mapping, `cosmyx` for rows added here).

allowlist row: kept on purpose, with a reason whose category comes first
(`credit: ...`):

- `{"kind": "msgid", "msgid", "reason"}`: a msgid that keeps the name.
- `{"kind": "literal", "file", "literal", "count", "reason"}`: a C++ literal
  (its source text between the quotes) and its exact count in that file.
- `{"kind": "text", "file", "text", "count", "reason"}`: a translated element
  of a setup-guide page.

inflection row: `{"language", "old", "new", "source"}`: in the translations
of one catalogue language, the exact text `old` (an inflected upstream name
such as cs "OrcaSliceru", or a longer phrase around it when the words next to
the name must change too) becomes `new`. Rows are written by a speaker of
that language, never guessed: an inflected name without its row is reported
by G8 as "needs inflection row".
"""

from __future__ import annotations

from .. import BrandingError, check_relative
import re

from .tokens import NEW_NAME, TOKEN, has_token

RENAME_KINDS = ("msgid", "literal")
ALLOW_KINDS = {"msgid": ("msgid",), "literal": ("file", "literal", "count"), "text": ("file", "text", "count")}
INFLECTION_KEYS = ("language", "old", "new")
_LANGUAGE = re.compile(r"[a-z]{2,3}(?:_[A-Z]{2})?")
# Every inflected form of the new name starts with this stem.
NEW_STEM = NEW_NAME[:-1]
REASON_CATEGORIES = frozenset(
    {"asset", "cli", "compared", "credit", "dev-tool", "external", "internal", "kept-name", "persisted", "url"}
)


def rename_rows(rows: list) -> list[dict]:
    """Validated rename rows: no identity, no duplicate old or new, no chain."""
    checked = []
    for row in rows:
        if not isinstance(row, dict) or row.get("kind") not in RENAME_KINDS:
            raise BrandingError(f"rename row needs kind {RENAME_KINDS}: {row!r}")
        old, new = row.get("old"), row.get("new")
        if not isinstance(old, str) or not isinstance(new, str) or not old:
            raise BrandingError(f"rename row needs string old and new: {row!r}")
        if old == new:
            raise BrandingError(f"rename row with identical old and new: {old!r}")
        if not has_token(old):
            raise BrandingError(f"rename row old does not name the upstream product: {old!r}")
        if NEW_NAME not in new:
            raise BrandingError(f"rename row new does not name {NEW_NAME}: {new!r}")
        checked.append(row)
    olds = [row["old"] for row in checked]
    news = [row["new"] for row in checked]
    for label, values in (("old", olds), ("new", news)):
        duplicates = sorted({value for value in values if values.count(value) > 1})
        if duplicates:
            raise BrandingError(f"duplicate rename {label}: {duplicates!r}")
    chained = sorted(set(olds) & set(news))
    if chained:
        raise BrandingError(f"rename chain (a new text is also an old one): {chained!r}")
    return checked


def inflection_rows(rows: list) -> list[dict]:
    """Validated inflection rows: an inflected upstream name in `old`, none in
    `new`, the new stem in `new`, one row per (language, old)."""
    if not isinstance(rows, list):
        raise BrandingError(f"inflection rows must be a list: {rows!r}")
    checked = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(key), str) for key in INFLECTION_KEYS):
            raise BrandingError(f"inflection row needs string {INFLECTION_KEYS}: {row!r}")
        language, old, new = (row[key] for key in INFLECTION_KEYS)
        if not _LANGUAGE.fullmatch(language):
            raise BrandingError(f"inflection row language must be a catalogue language such as cs or pt_BR: {row!r}")
        if not any(match.group("suffix") for match in TOKEN.finditer(old)):
            raise BrandingError(f"inflection row old has no inflected upstream name: {old!r}")
        if has_token(new) or NEW_STEM not in new:
            raise BrandingError(f"inflection row new must name {NEW_NAME} (stem {NEW_STEM!r}) and not the upstream product: {new!r}")
        if (language, old) in seen:
            raise BrandingError(f"duplicate inflection row: {language} {old!r}")
        seen.add((language, old))
        checked.append(row)
    return checked


def allow_rows(rows: list) -> list[dict]:
    checked = []
    seen = set()
    for row in rows:
        kind = row.get("kind") if isinstance(row, dict) else None
        if kind not in ALLOW_KINDS:
            raise BrandingError(f"allowlist row needs kind {tuple(ALLOW_KINDS)}: {row!r}")
        for key in ALLOW_KINDS[kind]:
            if key not in row:
                raise BrandingError(f"allowlist row lacks {key}: {row!r}")
        if "file" in row:
            check_relative(row["file"])
        if "count" in row and (not isinstance(row["count"], int) or isinstance(row["count"], bool) or row["count"] < 1):
            raise BrandingError(f"allowlist row count must be a positive integer: {row!r}")
        reason = row.get("reason")
        if not isinstance(reason, str) or reason.split(":", 1)[0] not in REASON_CATEGORIES:
            raise BrandingError(f"allowlist row reason must start with one of {sorted(REASON_CATEGORIES)}: {row!r}")
        key = tuple(row.get(name) for name in ("kind", "file", "msgid", "literal", "text"))
        if key in seen:
            raise BrandingError(f"duplicate allowlist row: {row!r}")
        seen.add(key)
        checked.append(row)
    return checked


def mapping(rows: list, kind: str | None = None) -> dict:
    return {row["old"]: row["new"] for row in rows if kind is None or row["kind"] == kind}
