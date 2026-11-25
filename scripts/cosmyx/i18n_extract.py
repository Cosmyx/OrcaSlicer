"""Extract the Cosmyx strings into per-feature catalogues.

Commands:

- `extract`: run xgettext over every source file under a `Cosmyx` folder of
  src/ (src/**/Cosmyx/**), one template per feature, written to
  localization/cosmyx/<feature>/messages.pot. Then refresh every
  localization/cosmyx/<feature>/<lang>.po, one per language folder of
  localization/i18n: new msgids are added untranslated, removed ones are
  dropped, existing translations are kept. Needs GNU xgettext; without it, use
  `just i18n-extract-docker`.
- `seed --ref REF`: fill the empty msgstr of the Cosmyx catalogues from the
  OrcaSlicer catalogues of a git ref (the old Cosmyx branch kept its strings
  there). Only exact (msgctxt, msgid) matches with a translated, non-fuzzy
  entry are copied. Needs git only.

Strings OrcaSlicer already has in localization/i18n/OrcaSlicer.pot are left
out of the Cosmyx templates: OrcaSlicer translates them already.

The feature of a source file is decided by `feature_for()`, the one place that
maps sources to features.

Standard library only. Shares the PO reader and writer of i18n_graft.py.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from i18n_graft import LANGUAGES_DIR_NAME, Catalogue, Entry, PoError, all_languages, parse_po, read_po, write_text  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

# Same keywords as the upstream gettext_make_pot target (CMakeLists.txt).
XGETTEXT_KEYWORDS = ["L", "_L", "_u8L", "L_CONTEXT:1,2c", "_L_CONTEXT:1,2c", "_u8L_CONTEXT:1,2c", "_L_PLURAL:1,2"]
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".mm", ".m"}

# Source file stems whose feature is not their own kebab-case name.
STEM_FEATURES = {
    "CosmyxAbout": "version",
}

MISSING_XGETTEXT = (
    "xgettext (GNU gettext) is not installed, so the Cosmyx templates cannot be extracted here.\n"
    "Install gettext (Debian/Ubuntu: apt install gettext; macOS: brew install gettext; "
    "Windows: MSYS2 pacman -S gettext), or run `just i18n-extract-docker`, which needs only Docker."
)


def kebab(name: str) -> str:
    """CamelCase or snake_case to kebab-case: BedTemperatureOff -> bed-temperature-off."""
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", name)
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def base_name(path: Path) -> str:
    """The kebab-case stem without a leading `cosmyx-`."""
    name = kebab(path.stem)
    return name[len("cosmyx-") :] if name.startswith("cosmyx-") else name


def feature_for(path: Path, known: set[str]) -> str:
    """The feature a Cosmyx source file belongs to.

    1. An explicit entry of STEM_FEATURES.
    2. Else the kebab-case stem without a leading `cosmyx-`
       (ChtNozzle.cpp -> cht-nozzle, CosmyxModels.cpp -> models).
    3. If a known feature is a word prefix of that name, the shortest such
       feature
       (CosmyxModelsMenu.cpp -> models). Known features are the folders of
       localization/cosmyx plus the base names of every Cosmyx source file,
       so CosmyxModels.cpp makes `models` known.
    """
    if path.stem in STEM_FEATURES:
        return STEM_FEATURES[path.stem]
    name = base_name(path)
    # The shortest prefix wins, so a file never becomes its own sub-feature.
    for feature in sorted(known, key=lambda f: (len(f), f)):
        if name == feature or name.startswith(feature + "-"):
            return feature
    return name


def cosmyx_sources(src_root: Path) -> list[Path]:
    """Every source file below a folder named Cosmyx, relative to src_root."""
    files = [
        path.relative_to(src_root)
        for path in src_root.rglob("*")
        if path.is_file() and path.suffix in SOURCE_SUFFIXES and "Cosmyx" in path.relative_to(src_root).parts[:-1]
    ]
    return sorted(files, key=lambda p: p.as_posix())


def languages(i18n_dir: Path) -> dict[str, Path]:
    """Every language with a catalogue: OrcaSlicer's, plus the ones Cosmyx adds
    in the sibling cosmyx/i18n folder (decision 0220)."""
    return all_languages(i18n_dir, i18n_dir.parent / "cosmyx")


def run_xgettext(xgettext: str, src_root: Path, files: list[Path], output: Path) -> None:
    command = [xgettext, *[f"--keyword={k}" for k in XGETTEXT_KEYWORDS]]
    command += ["--language=C++", "--add-comments=TRN", "--from-code=UTF-8", "--no-location", "--debug", "--boost"]
    command += ["--force-po", "--package-name=OrcaSlicer-Cosmyx", "-o", str(output)]
    command += [p.as_posix() for p in files]
    subprocess.run(command, cwd=src_root, check=True)


def _strip_date(text: str) -> str:
    return re.sub(r'^"POT-Creation-Date: .*\n', "", text, flags=re.MULTILINE)


def filter_template(template: Catalogue, upstream_keys: set) -> Catalogue:
    template.entries = [e for e in template.entries if not (e.is_message and e.key in upstream_keys)]
    return template


def plural_count(orca_po: Path) -> int:
    match = re.search(r"nplurals\s*=\s*(\d+)", read_po(orca_po).header_field("Plural-Forms") or "")
    return int(match.group(1)) if match else 2


def new_header(feature: str, orca_po: Path) -> Entry:
    orca = read_po(orca_po)
    fields = [
        f"Project-Id-Version: OrcaSlicer Cosmyx {feature}",
        f"Language: {orca.header_field('Language') or orca_po.parent.name}",
        "MIME-Version: 1.0",
        "Content-Type: text/plain; charset=UTF-8",
        "Content-Transfer-Encoding: 8bit",
    ]
    plural = orca.header_field("Plural-Forms")
    if plural:
        fields.append(f"Plural-Forms: {plural}")
    return Entry(msgid="", msgstr="".join(f"{line}\n" for line in fields))


def merge_language(template: Catalogue, existing: Catalogue | None, header: Entry, nplurals: int) -> Catalogue:
    """The <lang>.po for a template: template order and comments, existing
    translations and translator comments kept, new entries untranslated."""
    old = {e.key: e for e in existing.messages()} if existing else {}
    entries = [existing.header if existing and existing.header else header]
    for source in template.messages():
        previous = old.get(source.key)
        entry = Entry(
            comments=[c for c in source.comments if not c.startswith("# ")],
            flags=[f for f in source.flags if f != "fuzzy"],
            msgctxt=source.msgctxt,
            msgid=source.msgid,
            msgid_plural=source.msgid_plural,
        )
        if source.is_plural:
            entry.msgstr_plural = {i: "" for i in range(nplurals)}
        if previous is not None and previous.is_plural == source.is_plural:
            entry.comments = [c for c in previous.comments if c.startswith("# ")] + entry.comments
            if previous.fuzzy:
                entry.flags.append("fuzzy")
            entry.msgstr = previous.msgstr
            if source.is_plural:
                entry.msgstr_plural.update(previous.msgstr_plural)
        entries.append(entry)
    return Catalogue(entries=entries)


def extract(root: Path, src_root: Path, xgettext: str, cosmyx_dir: Path | None = None) -> dict[str, int]:
    """Refresh every feature's template and language files. Returns msgid counts.

    cosmyx_dir defaults to <root>/localization/cosmyx; the sync test points it
    at a copy, so it can extract without touching the checkout."""
    cosmyx_dir = cosmyx_dir or root / "localization" / "cosmyx"
    i18n_dir = root / "localization" / "i18n"
    known = {p.name for p in cosmyx_dir.iterdir() if p.is_dir() and p.name != LANGUAGES_DIR_NAME} if cosmyx_dir.is_dir() else set()
    sources = cosmyx_sources(src_root)
    known |= {STEM_FEATURES.get(p.stem, base_name(p)) for p in sources}
    by_feature: dict[str, list[Path]] = {}
    for path in sources:
        by_feature.setdefault(feature_for(path, known), []).append(path)
    upstream_keys = {e.key for e in read_po(i18n_dir / "OrcaSlicer.pot").messages()}
    counts: dict[str, int] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for feature, files in sorted(by_feature.items()):
            raw_pot = Path(tmp) / f"{feature}.pot"
            run_xgettext(xgettext, src_root, files, raw_pot)
            template = filter_template(read_po(raw_pot), upstream_keys)
            if not template.messages():
                continue
            counts[feature] = len(template.messages())
            write_feature(cosmyx_dir / feature, feature, template, i18n_dir)
    existing = {p.name for p in cosmyx_dir.iterdir() if p.is_dir() and p.name != LANGUAGES_DIR_NAME} if cosmyx_dir.is_dir() else set()
    for feature in sorted(existing - set(counts)):
        print(f"warning: feature {feature!r} has no strings in the sources; its catalogues are left as they are", file=sys.stderr)
    return counts


def write_feature(folder: Path, feature: str, template: Catalogue, i18n_dir: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    pot = folder / "messages.pot"
    text = template.render()
    if pot.is_file():
        old = pot.read_text(encoding="utf-8")
        # Keep the old file when only the creation date moved.
        if _strip_date(old) == _strip_date(text):
            text = old
    write_text(pot, text)
    template = parse_po(text)
    for language, orca_po in sorted(languages(i18n_dir).items()):
        target = folder / f"{language}.po"
        existing = read_po(target) if target.is_file() else None
        merged = merge_language(template, existing, new_header(feature, orca_po), plural_count(orca_po))
        write_text(target, merged.render())


def git_show(root: Path, ref: str, path: str) -> str | None:
    # Read the repository at root, whatever GIT_DIR an outer process (a hook) set.
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")}
    completed = subprocess.run(["git", "show", f"{ref}:{path}"], cwd=root, env=env, capture_output=True, check=False)
    if completed.returncode != 0:
        return None
    return completed.stdout.decode("utf-8")


def seed_catalogue(catalogue: Catalogue, source: Catalogue) -> int:
    """Copy translations from source into the empty entries of catalogue."""
    found = {e.key: e for e in source.messages() if e.translated and not e.fuzzy}
    filled = 0
    for entry in catalogue.messages():
        if entry.translated or entry.key not in found:
            continue
        donor = found[entry.key]
        if donor.is_plural != entry.is_plural:
            continue
        entry.msgstr = donor.msgstr
        entry.msgstr_plural = dict(donor.msgstr_plural)
        entry.touch()
        filled += 1
    return filled


def seed(root: Path, ref: str) -> dict[str, dict[str, int]]:
    cosmyx_dir = root / "localization" / "cosmyx"
    filled: dict[str, dict[str, int]] = {}
    sources: dict[str, Catalogue | None] = {}
    for po in sorted(cosmyx_dir.glob("*/*.po")):
        language = po.stem
        if language not in sources:
            text = git_show(root, ref, f"localization/i18n/{language}/OrcaSlicer_{language}.po")
            sources[language] = parse_po(text) if text is not None else None
        if sources[language] is None:
            continue
        catalogue = read_po(po)
        count = seed_catalogue(catalogue, sources[language])
        if count:
            write_text(po, catalogue.render())
            filled.setdefault(po.parent.name, {})[language] = count
    return filled


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract and seed the Cosmyx translation catalogues.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this checkout)")
    sub = parser.add_subparsers(dest="command", required=True)
    ext = sub.add_parser("extract", help="refresh localization/cosmyx from the sources (needs xgettext)")
    ext.add_argument("--src-root", type=Path, default=None, help="folder holding the sources (default: <root>/src)")
    ext.add_argument("--xgettext", default=None, help="xgettext executable (default: found on PATH)")
    sd = sub.add_parser("seed", help="fill empty translations from the catalogues of a git ref")
    sd.add_argument("--ref", required=True, help="git ref whose localization/i18n holds the old translations")
    args = parser.parse_args(argv)

    try:
        if args.command == "extract":
            xgettext = args.xgettext or shutil.which("xgettext")
            if not xgettext:
                print(MISSING_XGETTEXT, file=sys.stderr)
                return 2
            counts = extract(args.root, args.src_root or args.root / "src", xgettext)
            for feature, count in counts.items():
                print(f"{feature}: {count} msgids")
            if not counts:
                print("No Cosmyx strings found.")
        else:
            filled = seed(args.root, args.ref)
            for feature, per_language in filled.items():
                print(f"{feature}: " + ", ".join(f"{lang} {n}" for lang, n in sorted(per_language.items())))
            if not filled:
                print(f"Nothing to fill from {args.ref}.")
    except (PoError, OSError, subprocess.CalledProcessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
