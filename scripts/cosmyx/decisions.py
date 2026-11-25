"""List the Cosmyx decision register (wiki/decisions/NNNN-slug.md).

Prints one line per decision: its number, its title and its file name, in
number order. Exits with an error if a file in the register does not follow
the naming scheme, so a misnamed decision is caught.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DECISIONS_DIR = REPO_ROOT / "wiki" / "decisions"
NAME_PATTERN = re.compile(r"^(\d{4})-[a-z0-9]+(?:-[a-z0-9]+)*\.md$")


def read_title(path: Path) -> str:
    """Return the decision title: the first heading, without its number."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return re.sub(r"^\d{4}\.\s*", "", line[2:]).strip()
    return ""


def list_decisions(directory: Path) -> tuple[list[tuple[str, str, str]], list[str]]:
    """Return (decisions, errors).

    decisions holds (number, title, file name) sorted by number; errors names
    every Markdown file that breaks the naming scheme or has no title.
    """
    decisions: list[tuple[str, str, str]] = []
    errors: list[str] = []
    if not directory.is_dir():
        return decisions, [f"missing directory: {directory.name}"]
    for path in sorted(directory.iterdir()):
        if path.suffix != ".md" or path.name == "README.md":
            continue
        match = NAME_PATTERN.match(path.name)
        if match is None:
            errors.append(f"bad file name: {path.name}")
            continue
        title = read_title(path)
        if not title:
            errors.append(f"no title: {path.name}")
            continue
        decisions.append((match.group(1), title, path.name))
    numbers = [number for number, _, _ in decisions]
    for number in sorted(set(numbers)):
        if numbers.count(number) > 1:
            errors.append(f"duplicate number: {number}")
    decisions.sort()
    return decisions, errors


def main() -> int:
    decisions, errors = list_decisions(DECISIONS_DIR)
    for number, title, name in decisions:
        print(f"{number}  {title}  ({name})")
    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
