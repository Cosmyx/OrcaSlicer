"""Report the Cosmyx translations that are still missing.

Reads every localization/cosmyx/<feature>/<lang>.po and lists, per feature
and language, the entries a user of that language would see in English:

- `untranslated`: an empty msgstr, or a plural entry with any empty form;
- `fuzzy`: a fuzzy entry, which gettext never shows;
- `same as source`: a msgstr equal to its msgid, which is untranslated too.

English catalogues (`en`, `en_*`) are skipped: their msgids are the text.
A msgid listed in i18n_coverage_allow.json (an acronym such as CHT, a proper
name) may stay empty or equal to its source, for every language (`"*"`) or
for the languages it is listed under.

The report never fails by default: it is a to-do list for the translation
pass. `--strict` exits 1 when any gap is left, which the test of the
repository catalogues does when COSMYX_I18N_STRICT=1 is set.

Standard library only. Shares the PO reader of i18n_graft.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from i18n_graft import PoError, read_po  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
ALLOW_FILE = Path(__file__).resolve().parent / "i18n_coverage_allow.json"


@dataclass(frozen=True)
class Gap:
    feature: str
    language: str
    reason: str
    msgctxt: str | None
    msgid: str


def is_english(language: str) -> bool:
    return language == "en" or language.startswith("en_")


def load_allow(path: Path) -> dict[str, set[str]]:
    """Language (or "*") -> msgids allowed to stay as their source."""
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {language: set(msgids) for language, msgids in data.items()}


def allowed(allow: dict[str, set[str]], language: str, msgid: str) -> bool:
    return msgid in allow.get("*", set()) or msgid in allow.get(language, set())


def gap_reason(entry) -> str | None:
    if entry.fuzzy:
        return "fuzzy"
    if not entry.translated:
        return "untranslated"
    if not entry.is_plural and entry.msgstr == entry.msgid:
        return "same as source"
    return None


def coverage(cosmyx_dir: Path, allow: dict[str, set[str]], languages: set[str] | None = None) -> tuple[list[Gap], int]:
    """The gaps of every non-English catalogue, and the number of entries checked."""
    gaps: list[Gap] = []
    checked = 0
    for po in sorted(cosmyx_dir.glob("*/*.po"), key=lambda p: p.as_posix()):
        language = po.stem
        if is_english(language) or (languages and language not in languages):
            continue
        for entry in read_po(po).messages():
            checked += 1
            reason = gap_reason(entry)
            if reason and not allowed(allow, language, entry.msgid):
                gaps.append(Gap(po.parent.name, language, reason, entry.msgctxt, entry.msgid))
    return gaps, checked


def render(gaps: list[Gap], checked: int) -> str:
    lines: list[str] = []
    current = None
    for gap in gaps:
        if (gap.feature, gap.language) != current:
            current = (gap.feature, gap.language)
            count = sum(1 for g in gaps if (g.feature, g.language) == current)
            lines.append(f"{gap.feature}/{gap.language}.po: {count} missing")
        context = f"[{gap.msgctxt}] " if gap.msgctxt else ""
        first_line = gap.msgid.splitlines()[0] if gap.msgid else ""
        lines.append(f"  {gap.reason}: {context}{first_line}")
    lines.append(f"{len(gaps)} missing of {checked} entries checked.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="List the Cosmyx translations still missing.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this checkout)")
    parser.add_argument("--lang", action="append", help="only this language (repeatable)")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any translation is missing")
    args = parser.parse_args(argv)
    try:
        gaps, checked = coverage(args.root / "localization" / "cosmyx", load_allow(ALLOW_FILE), set(args.lang or []))
    except (PoError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(render(gaps, checked))
    return 1 if args.strict and gaps else 0


if __name__ == "__main__":
    sys.exit(main())
