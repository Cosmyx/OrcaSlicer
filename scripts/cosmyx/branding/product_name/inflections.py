"""List the inflected upstream names that need an inflection row (`just brand-name-inflections`).

    python scripts/cosmyx/branding/product_name/inflections.py [--root DIR] [--out FILE]

On the (unbranded) tree, for every catalogue language: every distinct
inflected upstream name ("OrcaSliceru", "OrcaSlicerrel"...) left in a
confirmed translation of a renamed msgid that no row of
`cosmyx-src/branding/product-name/inflections.json` renames yet, with how
often it appears and one example (msgid and translation). Hyphenated forms
("OrcaSlicer-ben") are listed apart: they are renamed to "CosmoSlice-ben"
today, and need a row only when the suffix must change with the new name.

The output is JSON, for a speaker of each language to write the rows. It
writes nothing else: the replacement forms are never guessed. Standard
library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from branding import PRODUCT_NAME_DIR, load_json, repo_path, write_text  # noqa: E402
    from branding import product_name  # noqa: E402
    from branding.product_name import catalogues, tables  # noqa: E402
    from branding.product_name.tokens import TOKEN, inflection_map, protected_spans, unresolved  # noqa: E402
else:
    from .. import PRODUCT_NAME_DIR, load_json, repo_path, write_text
    from .. import product_name
    from . import catalogues, tables
    from .tokens import TOKEN, inflection_map, protected_spans, unresolved

# The name, a hyphen and a lowercase suffix ("OrcaSlicer-ben").
_HYPHENATED = re.compile(TOKEN.pattern.replace("(?P<suffix>", "-(?P<suffix>", 1).replace("]*)", "]+)", 1))


def _entry(form: str, msgid: str, text: str) -> dict:
    return {"form": form, "count": 0, "example_msgid": msgid, "example_translation": text}


def needed(root: Path) -> dict:
    """{language: {"inflected": [...], "hyphenated": [...]}}, each item
    {form, count, example_msgid, example_translation}, sorted by form."""
    path = repo_path(root, f"{PRODUCT_NAME_DIR}/rename.json")
    rename = tables.rename_rows(load_json(path)["rows"]) if path.is_file() else []
    inflections = inflection_map(product_name.load_inflections(root))
    msgids = {row["old"] for row in rename if row["kind"] == "msgid"}
    found: dict = {}
    for _, lang, msgid, text in catalogues.renamed_translations(root, msgids):
        groups = found.setdefault(lang, {"inflected": {}, "hyphenated": {}})
        for form in unresolved(text, lang, inflections):
            groups["inflected"].setdefault(form, _entry(form, msgid, text))["count"] += 1
        spans = protected_spans(text)
        for match in _HYPHENATED.finditer(text):
            if not any(low <= match.start() and match.end() <= high for low, high in spans):
                form = match.group(0)
                groups["hyphenated"].setdefault(form, _entry(form, msgid, text))["count"] += 1
    return {
        lang: {kind: [items[form] for form in sorted(items)] for kind, items in groups.items()}
        for lang, groups in sorted(found.items())
        if groups["inflected"] or groups["hyphenated"]
    }


def main(argv: list[str] | None = None, out=print) -> int:
    parser = argparse.ArgumentParser(description="List the inflected product names that need an inflection row.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument("--out", type=Path, help="write the JSON to this file instead of printing it")
    args = parser.parse_args(argv)
    text = json.dumps(needed(args.root.resolve()), indent=2, ensure_ascii=False) + "\n"
    if args.out:
        write_text(args.out, text)
    else:
        out(text.rstrip("\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
