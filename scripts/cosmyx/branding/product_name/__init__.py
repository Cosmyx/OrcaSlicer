"""Product-name stage of the branding engine (T11e): OrcaSlicer -> CosmoSlice.

The engine applies the `patches` rows first (build files, packaging, the
display-name macros, the machine-read sites rewired to SLIC3R_APP_KEY). This
plugin then renames, from the `rename` table:

- every C++ literal (adjacent literals joined) and every hint whose value is
  an old text, and the same msgid in the template and every catalogue, the
  translations' product name included, never marking anything fuzzy;
- checked by its guards (G8):
  - pre: every rename row still matches (a msgid row: its msgid in the
    template and its text in the sources, the new msgid not there yet; a
    literal row: its text in the sources and no msgid); every allowlist row
    still matches with its exact count. A stale row is an error.
  - pre: every inflection row still matches a confirmed translation of a
    renamed msgid in its language.
  - post: literal and msgid renamed together (old gone everywhere, new in
    both); no renamed translation still names the upstream product (an
    inflected name without its inflection row is reported as "needs
    inflection row": a warning on development builds, an error on release
    builds, decision 0135); and no
    visible text names it (non-log C++ literals, template msgids, hints,
    setup-guide pages) outside the allowlist. A new upstream text is drift:
    a warning on development builds, an error on release builds.

Tables: `cosmyx-src/branding/product-name/{rename,allowlist,patches,inflections}.json`.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from .. import PRODUCT_NAME_DIR, BrandingError, Finding, encode_text, load_json, is_cosmyx_path, line_ending, read_lf, relative_posix, repo_path
from . import catalogues, cpp, resources, tables
from .tokens import NEW_NAME, inflection_map, replace_tokens, unresolved, visible_name

GUARD = "G8"
SOURCE_DIR = "src"
CPP_SUFFIXES = frozenset({".cpp", ".hpp", ".h", ".mm", ".c", ".cc", ".cxx", ".hxx"})
# Cheap pre-filter: a file without these cannot name either product.
_CANDIDATE = re.compile(r"Orc|ORCA|CosmoSlice")


# ---------------------------------------------------------------- tables


def load_tables(ctx) -> tuple[list, list]:
    data = ctx.product_name or {}
    return tables.rename_rows(data.get("rename", [])), tables.allow_rows(data.get("allowlist", []))


INFLECTIONS_FILE = f"{PRODUCT_NAME_DIR}/inflections.json"


def load_inflections(root: Path) -> list:
    """Validated inflection rows of the tree (none when the table is absent)."""
    path = repo_path(root, INFLECTIONS_FILE)
    if not path.is_file():
        return []
    data = load_json(path)
    if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("rows"), list):
        raise BrandingError(f'{INFLECTIONS_FILE}: expected {{"schema": 1, "rows": [...]}}')
    return tables.inflection_rows(data["rows"])


def drift_level(ctx) -> str:
    return "error" if ctx.kind == "release" else "warning"


# ---------------------------------------------------------------- sources


def source_files(root: Path) -> list[str]:
    """C++ sources under src/ that may name the product (Cosmyx files left out)."""
    base = repo_path(root, SOURCE_DIR)
    if not base.is_dir():
        return []
    found = []
    for path in base.rglob("*"):
        if path.suffix not in CPP_SUFFIXES or not path.is_file():
            continue
        relative = relative_posix(root, path)
        if is_cosmyx_path(relative):
            continue
        if _CANDIDATE.search(path.read_bytes().decode("utf-8", "replace")):
            found.append(relative)
    return sorted(found)


def read_source(root: Path, relative: str) -> str:
    """A C++ source as LF text: a CRLF checkout (Windows) reads the same."""
    return read_lf(repo_path(root, relative), "surrogateescape")


def write_like(root: Path, relative: str, text: str, errors: str = "strict") -> None:
    """Write LF `text` over a file with that file's own dominant line ending."""
    path = repo_path(root, relative)
    eol = line_ending(path.read_bytes()).decode("ascii")
    path.write_bytes(encode_text(text, eol, errors))


def source_groups(root: Path) -> list[tuple[str, cpp.Group]]:
    found = []
    for relative in source_files(root):
        found += [(relative, group) for group in cpp.groups(read_source(root, relative), relative)]
    return found


def text_counts(root: Path, sources: list) -> Counter:
    """{decoded text: occurrences} over C++ literal groups and hints."""
    counts = Counter(group.value for _, group in sources)
    counts.update(resources.hint_texts(root).values())
    return counts


def template_msgids(root: Path) -> Counter:
    counts = Counter()
    for relative in catalogues.catalogue_files(root):
        if relative.endswith(".pot"):
            counts.update(catalogues.msgids(catalogues.read(root, relative)))
    return counts


# ---------------------------------------------------------------- apply


def apply(ctx, backup) -> dict:
    rename, _ = load_tables(ctx)
    mapping = tables.mapping(rename)
    root = ctx.root
    inflections = inflection_map(load_inflections(root))
    written: dict = {}
    for relative in source_files(root):
        text = read_source(root, relative)
        new_text, counts = cpp.rename(text, mapping, relative)
        if counts:
            written[relative] = new_text
    hints = repo_path(root, resources.HINTS_FILE)
    if hints.is_file():
        try:
            hint_text = read_lf(hints)
        except UnicodeDecodeError as error:
            raise BrandingError(f"{resources.HINTS_FILE} is not UTF-8: {error}") from error
        new_text, counts = resources.rename_hints(hint_text, mapping)
        if counts:
            written[resources.HINTS_FILE] = new_text
    renamed = catalogues.plan(root, tables.mapping(rename, "msgid"), inflections)
    # Everything is computed before the first write; the engine reverts the
    # backups if anything fails afterwards.
    for relative, text in sorted(written.items()):
        backup(relative)
        write_like(root, relative, text, "surrogateescape")
    for relative, (text, _) in sorted(renamed.items()):
        backup(relative)
        write_like(root, relative, text)
    return {
        "rows": len(rename),
        "sources": sorted(written),
        "catalogues": {relative: changed for relative, (_, changed) in sorted(renamed.items())},
        "needs_inflection": needs_inflection(root, rename, inflections),
    }


def needs_inflection(root: Path, rename: list, inflections: dict) -> dict:
    """{language: [inflected forms no row renames]} over the confirmed
    translations of the renamed msgids (old or new msgid: before or after apply)."""
    msgids = {row[key] for row in rename if row["kind"] == "msgid" for key in ("old", "new")}
    found: dict = {}
    for _, lang, _, text in catalogues.renamed_translations(root, msgids):
        for form in unresolved(text, lang, inflections):
            found.setdefault(lang, set()).add(form)
    return {lang: sorted(forms) for lang, forms in sorted(found.items())}


# ---------------------------------------------------------------- guards


def guards(ctx, phase: str) -> list[Finding]:
    root = ctx.root
    try:
        rename, allow = load_tables(ctx)
        inflections = load_inflections(root)
    except BrandingError as error:
        return [Finding(GUARD, "error", PRODUCT_NAME_DIR, str(error))]
    try:
        sources = source_groups(root)
        pot = template_msgids(root)
        texts = text_counts(root, sources)
        findings = check_rename(rename, texts, pot, phase)
        findings += check_allowlist(ctx, allow, sources, pot, texts, phase, {row["new"] for row in rename})
        if phase == "pre":
            findings += check_inflections(root, rename, inflections)
        else:
            findings += check_translations(root, rename, inflection_map(inflections), drift_level(ctx))
    except (BrandingError, OSError) as error:
        return [Finding(GUARD, "error", "", str(error))]
    except UnicodeDecodeError as error:
        # A file that is not UTF-8 (hints, a guide page): a clean finding, no traceback.
        return [Finding(GUARD, "error", "", f"a product-name input is not UTF-8: {error}")]
    return findings


def check_rename(rename: list, texts: Counter, pot: Counter, phase: str) -> list[Finding]:
    findings = []
    where = "cosmyx-src/branding/product-name/rename.json"
    for row in rename:
        old, new, kind = row["old"], row["new"], row["kind"]
        label = f"{kind} row {old[:60]!r}"
        if phase == "pre":
            if not texts[old]:
                findings.append(Finding(GUARD, "error", where, f"stale {label}: no C++ literal or hint has this text"))
            if kind == "msgid" and not pot[old]:
                findings.append(Finding(GUARD, "error", where, f"stale {label}: the template has no such msgid"))
            if kind == "literal" and pot[old]:
                findings.append(Finding(GUARD, "error", where, f"{label} is a msgid: make it a msgid row"))
            if kind == "msgid" and pot[new]:
                findings.append(Finding(GUARD, "error", where, f"{label}: the new msgid already exists"))
        else:
            if texts[old] or pot[old]:
                findings.append(Finding(GUARD, "error", where, f"{label}: old text left after apply"))
            if not texts[new]:
                findings.append(Finding(GUARD, "error", where, f"{label}: no literal or hint carries the new text"))
            if kind == "msgid" and not pot[new]:
                findings.append(Finding(GUARD, "error", where, f"{label}: literal renamed but not its msgid"))
    return findings


def check_allowlist(ctx, allow: list, sources: list, pot: Counter, texts: Counter, phase: str, renamed: set) -> list[Finding]:
    where = "cosmyx-src/branding/product-name/allowlist.json"
    kept_msgids = {row["msgid"] for row in allow if row["kind"] == "msgid"}
    findings = [
        Finding(GUARD, "error", where, f"stale msgid row {msgid[:60]!r}: the template has no such msgid")
        for msgid in sorted(kept_msgids)
        if not pot[msgid] and not (phase == "pre" and msgid in renamed)
    ]
    level = drift_level(ctx)

    # C++ literals: every non-log, non-include literal naming the product.
    found = Counter()
    for relative, group in sources:
        if group.value in kept_msgids:
            continue
        for piece in group.pieces:
            if visible_name(piece.raw) and not piece.is_log and not piece.is_include:
                found[(relative, piece.raw)] += 1
    allowed = Counter({(row["file"], row["literal"]): row["count"] for row in allow if row["kind"] == "literal"})
    findings += compare(found, allowed, phase, level, "literal")

    # Setup-guide pages.
    guide = Counter((path, text) for path, _, text in resources.guide_texts(ctx.root) if visible_name(text))
    allowed = Counter({(row["file"], row["text"]): row["count"] for row in allow if row["kind"] == "text"})
    findings += compare(guide, allowed, phase, level, "guide text")

    if phase == "post":
        # A template msgid no source carries any more is never shown.
        shown = (msgid for msgid in pot if texts[msgid] and msgid not in kept_msgids)
        for msgid in sorted(msgid for msgid in shown if visible_name(msgid)):
            findings.append(Finding(GUARD, level, catalogues.CATALOGUE_DIR, f"msgid names the upstream product: {msgid[:80]!r}"))
        for section, text in sorted(resources.hint_texts(ctx.root).items()):
            if visible_name(text) and text not in kept_msgids:
                findings.append(Finding(GUARD, level, resources.HINTS_FILE, f"[{section}] names the upstream product"))
    return findings


def compare(found: Counter, allowed: Counter, phase: str, level: str, label: str) -> list[Finding]:
    """Stale allowlist rows (pre and post); visible residue (post only)."""
    findings = []
    for (path, text), count in sorted(allowed.items()):
        if found[(path, text)] < count:
            findings.append(
                Finding(GUARD, "error", path, f"stale allowlist {label} {text[:60]!r}: {found[(path, text)]} found, {count} listed")
            )
    if phase == "post":
        for (path, text), count in sorted(found.items()):
            if count > allowed[(path, text)]:
                findings.append(Finding(GUARD, level, path, f"{label} names the upstream product: {text[:80]!r}"))
    return findings


def check_inflections(root: Path, rename: list, rows: list) -> list[Finding]:
    """Pre: every inflection row matches a confirmed translation of a renamed
    msgid in its language; a row that matches none is stale."""
    msgids = {row["old"] for row in rename if row["kind"] == "msgid"}
    texts: dict = {}
    for _, lang, _, text in catalogues.renamed_translations(root, msgids):
        texts.setdefault(lang, []).append(text)
    return [
        Finding(GUARD, "error", INFLECTIONS_FILE, f"stale inflection row {row['language']} {row['old']!r}: no renamed translation has it")
        for row in rows
        if not any(row["old"] in text for text in texts.get(row["language"], []))
    ]


def check_translations(root: Path, rename: list, inflections: dict | None = None, level: str = "warning") -> list[Finding]:
    """No confirmed translation of a renamed msgid still names the upstream product.

    An inflected name left only because its inflection row is missing is
    reported as "needs inflection row" at `level` (the drift level: a speaker
    of the language writes the row); any other name left is an error.
    `inflections` defaults to the tree's own table."""
    if inflections is None:
        inflections = inflection_map(load_inflections(root))
    renamed = {row["new"] for row in rename if row["kind"] == "msgid"}
    findings = []
    for relative, lang, msgid, text in catalogues.renamed_translations(root, renamed):
        left = unresolved(text, lang, inflections)
        if left:
            forms = ", ".join(sorted(set(left)))
            findings.append(
                Finding(GUARD, level, relative, f"needs inflection row ({lang}): {forms} in {msgid[:60]!r}; add it to {INFLECTIONS_FILE}")
            )
        if replace_tokens(text, lang, inflections=inflections) != text:
            findings.append(Finding(GUARD, "error", relative, f"translation still names the upstream product: {msgid[:60]!r}"))
    return findings


__all__ = ["NEW_NAME", "apply", "guards"]
