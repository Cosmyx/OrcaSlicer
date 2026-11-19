"""Propose product-name table rows for what upstream added (`just brand-name-candidates`).

    python scripts/cosmyx/branding/product_name/candidates.py [--root DIR]

Prints, as JSON, what the tables do not cover yet on the (unbranded) tree:

- `rename`: a proposed msgid row for every template msgid a source still
  carries that names the upstream product, with the name replaced;
- `literals`: every other visible C++ literal naming the product, to turn into
  a rename `literal` row, a patch row, or an allowlist row with its reason;
- `stale`: rename rows whose old text is gone.

It writes nothing: a person or an agent reviews the proposals (a credit or a
name upstream keeps on purpose goes to the allowlist instead) and adds them to
`cosmyx-src/branding/product-name/`. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from branding import PRODUCT_NAME_DIR, load_json, repo_path  # noqa: E402
    from branding import product_name  # noqa: E402
    from branding.product_name import tables  # noqa: E402
    from branding.product_name.tokens import replace_tokens, visible_name  # noqa: E402
else:
    from .. import PRODUCT_NAME_DIR, load_json, repo_path
    from .. import product_name
    from . import tables
    from .tokens import replace_tokens, visible_name


def load_rows(root: Path, name: str) -> list:
    path = repo_path(root, f"{PRODUCT_NAME_DIR}/{name}.json")
    return load_json(path)["rows"] if path.is_file() else []


def propose(root: Path) -> dict:
    rename = tables.rename_rows(load_rows(root, "rename"))
    allow = tables.allow_rows(load_rows(root, "allowlist"))
    covered = {row["old"] for row in rename} | {row["new"] for row in rename}
    kept = {row["msgid"] for row in allow if row["kind"] == "msgid"}
    allowed = Counter({(row["file"], row["literal"]): row["count"] for row in allow if row["kind"] == "literal"})
    sources = product_name.source_groups(root)
    pot = product_name.template_msgids(root)
    texts = product_name.text_counts(root, sources)

    proposals = [
        {"kind": "msgid", "old": msgid, "new": replace_tokens(msgid), "source": "cosmyx"}
        for msgid in sorted(pot)
        if texts[msgid] and msgid not in covered and msgid not in kept and visible_name(msgid)
    ]
    found = Counter()
    values: dict = {}
    for relative, group in sources:
        if group.value in covered or group.value in kept or group.value in pot:
            continue
        for piece in group.pieces:
            if visible_name(piece.raw) and not piece.is_log and not piece.is_include:
                found[(relative, piece.raw)] += 1
                values.setdefault((relative, piece.raw), group.value)
    # Literals a patch row rewrites are covered too.
    for row in load_rows(root, "patches"):
        for key in list(found):
            if key[0] == row["file"] and f'"{key[1]}"' in row["old"]:
                found[key] -= row["count"]
    literals = [
        {"file": relative, "literal": raw, "count": count, "value": values[(relative, raw)]}
        for (relative, raw), count in sorted(found.items())
        if count > allowed[(relative, raw)]
    ]
    stale = [row["old"] for row in rename if not texts[row["old"]]]
    return {"rename": proposals, "literals": literals, "stale": stale}


def main(argv: list[str] | None = None, out=print) -> int:
    parser = argparse.ArgumentParser(description="Propose product-name table rows.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[4])
    args = parser.parse_args(argv)
    out(json.dumps(propose(args.root.resolve()), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
