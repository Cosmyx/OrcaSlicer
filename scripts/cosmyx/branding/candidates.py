"""SVG recolour candidates of the Cosmyx branding engine (T11d).

The colour stage (colours.py) rewrites the teal in C++ and web sources at
build time, but the SVG icons under resources/images and resources/web keep
their teal unless an overlay file replaces them. This tool proposes those
overlay files, and never commits anything by itself:

1. `generate` writes one candidate per `recolour` manifest row that has no
   overlay yet (`missing`) into build/cosmyx/candidates/<repository path>,
   plus `candidates.json` (the index the other commands read). Each candidate
   is the upstream file with every `#RRGGBB` of a *validated* colours.json
   mapping replaced by its target, in uppercase, only inside attribute values,
   `style="..."` attributes and the declaration blocks of `<style>` elements;
   never in an `id` or `href` attribute, a `url(...)` reference, a URL
   fragment, a numeric character reference or base64 data (the T11a hex rule,
   `hex_is_skipped`). Teal left after the rewrite (a colour with no validated
   mapping) is reported per file, and teal SVGs that have no manifest row yet
   (guard G4) are reported and skipped until `just brand-sync`.
2. `review` writes a self-contained HTML sheet per group under
   build/cosmyx/review/ (and an index): each icon before and after, on
   #FFFFFF with the light colour map of BitmapCache.cpp and on #1C1C1F with
   its dark map, both read from the tree and branded the way the build
   brands them (the colours.json snippets and hex rewrite). Images are
   `<img>` tags with data URIs only, so the sheet opens offline.
3. `accept PATTERN` copies the matching candidates (a group name or an
   fnmatch glob on the path) into cosmyx-src/branding/overlay/ and records
   them in the manifest as source `candidate`, status `to-validate`. Only the
   user validates them afterwards (decision 0121).

Command line (the `just brand-candidates`, `brand-review` and `brand-accept`
recipes):

    python scripts/cosmyx/branding/candidates.py generate
    python scripts/cosmyx/branding/candidates.py review
    python scripts/cosmyx/branding/candidates.py accept PATTERN

Removing this file removes the three recipes; recolouring an icon then means
writing its overlay file by hand and running `just brand-sync`.
"""

from __future__ import annotations

if __package__ in (None, ""):
    # Run as a script: import this module through its package.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from branding.candidates import main

    raise SystemExit(main())

import argparse
import base64
import fnmatch
import html
import re
import shutil
import sys
from pathlib import Path

from . import (
    COLOURS_FILE,
    DEFAULT_FAMILY,
    DEFAULT_IGNORE,
    BrandingError,
    content_sha256,
    dump_json,
    file_sha256,
    find_hexes,
    in_family,
    load_json,
    repo_path,
    write_text,
)
from . import apply as apply_module
from . import colours as colours_module
from . import manifest as manifest_module
from . import render

CANDIDATES_DIR = "build/cosmyx/candidates"
INDEX_NAME = "candidates.json"
REVIEW_DIR = "build/cosmyx/review"
BITMAP_CACHE = "src/slic3r/GUI/BitmapCache.cpp"
CANDIDATE_GROUPS = ("icons-a-m", "icons-n-z", "web")
BACKGROUNDS = {"light": "#FFFFFF", "dark": "#1C1C1F"}
SCHEMA = 1

# ---------------------------------------------------------------- SVG rewrite

# Comments and CDATA outside <style> are copied as they are; a <style>
# element is rewritten in its declaration blocks; any other tag in its
# attribute values.
_TOKEN_RE = re.compile(
    r"<!--.*?-->"
    r"|<!\[CDATA\[.*?\]\]>"
    r"|(?P<style_open><style\b[^<>]*>)(?P<style_body>.*?)(?P<style_close></style\s*>)"
    r"|<[A-Za-z][^<>]*>",
    re.DOTALL | re.IGNORECASE,
)
_ATTRIBUTE_RE = re.compile(r"""(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)(?P<eq>\s*=\s*)(?P<value>"[^"]*"|'[^']*')""")
_DECLARATIONS_RE = re.compile(r"\{[^{}]*\}")


def attribute_skipped(name: str) -> bool:
    """`id` and every `href` (`href`, `xlink:href`) never change."""
    lowered = name.lower()
    return lowered == "id" or lowered == "href" or lowered.endswith(":href")


def recolour_svg(text: str, table: dict) -> tuple:
    """Rewrite the mapped colours of an SVG text. Returns (text, {from: count}).

    `table` maps uppercase `#RRGGBB` to uppercase `#RRGGBB`.
    """
    counts: dict = {}

    def rewrite(fragment: str) -> str:
        data, found = colours_module.rewrite_hex(fragment.encode("utf-8", "surrogateescape"), table)
        for colour, count in found.items():
            counts[colour] = counts.get(colour, 0) + count
        return data.decode("utf-8", "surrogateescape")

    def attributes(tag: str) -> str:
        def one(match: re.Match) -> str:
            if attribute_skipped(match.group("name")):
                return match.group(0)
            return match.group("name") + match.group("eq") + rewrite(match.group("value"))

        return _ATTRIBUTE_RE.sub(one, tag)

    def token(match: re.Match) -> str:
        whole = match.group(0)
        if whole.startswith("<!"):
            return whole
        if match.group("style_open") is not None:
            body = _DECLARATIONS_RE.sub(lambda block: rewrite(block.group(0)), match.group("style_body"))
            return attributes(match.group("style_open")) + body + match.group("style_close")
        return attributes(whole)

    return _TOKEN_RE.sub(token, text), counts


def teal_left(text: str, family: dict, ignore) -> list:
    """The teal colours still in `text`, uppercased, sorted, once each."""
    return sorted({colour for colour in find_hexes(text) if in_family(colour, family, ignore)})


# ---------------------------------------------------------------- tables


def load_colours(root: Path) -> dict:
    return colours_module.load_colours(root)


def validated_table(colours: dict) -> dict:
    """{from: to} of the validated mappings only: candidates never use a
    colour the user has not approved."""
    return {row["from"]: row["to"] for row in colours.get("mappings", []) if row.get("status") == "validated"}


def family_of(colours: dict) -> tuple:
    return colours.get("family") or DEFAULT_FAMILY, colours.get("ignore") or list(DEFAULT_IGNORE)


def colours_sha(root: Path) -> str:
    return file_sha256(repo_path(root, COLOURS_FILE), "svg")


def refuse_when_branded(root: Path) -> None:
    if apply_module.State(root).active:
        raise BrandingError("the tree is branded; run `just brand-revert` first")


def candidate_rows(root: Path) -> list:
    """(group, row) of every recolour SVG row without an overlay yet."""
    rows = []
    for group, row in manifest_module.load(root).rows():
        if group in CANDIDATE_GROUPS and row["kind"] == "recolour" and row["format"] == "svg" and row["status"] == "missing":
            rows.append((group, row))
    return rows


def unlisted_teal(root: Path, colours: dict) -> list:
    """Teal SVGs guard G4 would report: discovered upstream, no manifest row."""
    family, ignore = family_of(colours)
    listed = set(manifest_module.load(root).by_path())
    return sorted(path for path in manifest_module.discover(root, family, ignore) if path not in listed)


def candidate_path(root: Path, path: str) -> Path:
    return repo_path(root, f"{CANDIDATES_DIR}/{path}")


def index_path(root: Path) -> Path:
    return repo_path(root, f"{CANDIDATES_DIR}/{INDEX_NAME}")


def load_index(root: Path) -> dict:
    path = index_path(root)
    if not path.is_file():
        raise BrandingError(f"{CANDIDATES_DIR}/{INDEX_NAME} not found; run `just brand-candidates` first")
    data = load_json(path)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("candidates"), list):
        raise BrandingError(f"{CANDIDATES_DIR}/{INDEX_NAME} is not a schema {SCHEMA} index; run `just brand-candidates`")
    return data


def empty_in_place(directory: Path) -> None:
    """Delete the files under `directory`, keeping the folders: a folder
    deleted and recreated at once can fail on a network share."""
    if not directory.is_dir():
        return
    for path in sorted(directory.rglob("*"), reverse=True):
        if path.is_file() or path.is_symlink():
            path.unlink()


# ---------------------------------------------------------------- generate


def generate(root: Path) -> dict:
    """Write the candidates and their index. Returns the index."""
    refuse_when_branded(root)
    colours = load_colours(root)
    table = validated_table(colours)
    family, ignore = family_of(colours)
    out_dir = repo_path(root, CANDIDATES_DIR)
    empty_in_place(out_dir)
    entries, unchanged = [], []
    for group, row in candidate_rows(root):
        path = row["path"]
        upstream = repo_path(root, path)
        if not upstream.is_file():
            continue
        data = upstream.read_bytes()
        text = data.decode("utf-8", "surrogateescape")
        new_text, counts = recolour_svg(text, table)
        if not counts:
            unchanged.append({"path": path, "teal_left": teal_left(text, family, ignore)})
            continue
        new_data = new_text.encode("utf-8", "surrogateescape")
        target = candidate_path(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(new_data)
        entries.append(
            {
                "path": path,
                "group": group,
                "usage": row["usage"],
                "upstream_sha256": file_sha256(upstream),
                "candidate_sha256": content_sha256(new_data, "svg"),
                "replacements": dict(sorted(counts.items())),
                "teal_left": teal_left(new_text, family, ignore),
            }
        )
    index = {
        "schema": SCHEMA,
        "colours_sha256": colours_sha(root),
        "candidates": entries,
        "unchanged": unchanged,
        "unlisted": unlisted_teal(root, colours),
        "unvalidated_mappings": sorted(
            row["from"] for row in colours.get("mappings", []) if row.get("status") != "validated"
        ),
    }
    write_text(index_path(root), dump_json(index))
    return index


def generate_report(index: dict) -> list:
    lines = [f"{len(index['candidates'])} candidate(s) in {CANDIDATES_DIR}/."]
    for entry in index["candidates"]:
        if entry["teal_left"]:
            lines.append(f"warning: {entry['path']}: teal left without a validated mapping: {', '.join(entry['teal_left'])}")
    if index["unchanged"]:
        lines.append(f"{len(index['unchanged'])} row(s) with no validated mapping to apply (no candidate):")
        lines += [f"  {entry['path']}: teal {', '.join(entry['teal_left']) or 'none'}" for entry in index["unchanged"]]
    for path in index["unlisted"]:
        lines.append(f"warning: G4 {path}: teal SVG without a manifest row, skipped (just brand-sync)")
    if index["unvalidated_mappings"]:
        lines.append(f"Not used (to-validate): {', '.join(index['unvalidated_mappings'])}")
    return lines


# ---------------------------------------------------------------- review


_REPLACE_RE = re.compile(r'^\s*replaces\[("(?:[^"\\]|\\.)*")\]\s*=\s*("(?:[^"\\]|\\.)*")\s*;')


def _c_string(literal: str) -> str:
    """The value of a C++ string literal holding only `\\"` and `\\\\` escapes."""
    body = literal[1:-1]
    return re.sub(r"\\(.)", lambda match: match.group(1), body)


def parse_colour_maps(text: str) -> dict:
    """The fixed colour maps of BitmapCache::load_svg: {"light": {...}, "dark": {...}}.

    Reads the `replaces[...] = ...;` lines from the map declaration to the
    first `strstr(` (the per-icon and per-call cases after it are not
    simulated): lines before `if (dark_mode)` go to both maps, lines in that
    block to the dark map, lines in its `else` block to the light map.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    start = next((i for i, line in enumerate(lines) if "std::map<std::string, std::string> replaces;" in line), None)
    if start is None:
        raise BrandingError(f"{BITMAP_CACHE}: the colour map declaration was not found")
    maps = {"light": {}, "dark": {}}
    section = "both"
    for line in lines[start + 1 :]:
        if "strstr(" in line:
            break
        if re.search(r"\bif\s*\(\s*dark_mode\s*\)", line):
            section = "dark"
            continue
        if re.search(r"\}\s*else\s*\{", line):
            section = "light"
            continue
        match = _REPLACE_RE.match(line)
        if not match:
            continue
        key, value = _c_string(match.group(1)), _c_string(match.group(2))
        for name in ("light", "dark") if section == "both" else (section,):
            maps[name][key] = value
    if not maps["dark"]:
        raise BrandingError(f"{BITMAP_CACHE}: no dark colour map found")
    return maps


def branded_source(text: str, colours: dict) -> str:
    """BitmapCache.cpp as the build brands it: snippets, then the hex rewrite."""
    lines = text.replace("\r\n", "\n").split("\n")
    for row in colours.get("snippets", []):
        if row.get("file") != BITMAP_CACHE:
            continue
        result = []
        for line in lines:
            result.append(line)
            if line == row["anchor"]:
                result.append(row["insert"])
        lines = result
    data, _ = colours_module.rewrite_hex("\n".join(lines).encode("utf-8"), colours_module.mapping_table(colours))
    return data.decode("utf-8")


def apply_map(text: str, colour_map: dict) -> str:
    """Apply a map as BitmapCache does: std::map key order, replace all."""
    for key in sorted(colour_map):
        text = text.replace(key, colour_map[key])
    return text


def data_uri(text: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(text.encode("utf-8", "surrogateescape")).decode("ascii")


PAGE_STYLE = """
body { margin: 0; padding: 16px; font: 14px/1.4 system-ui, sans-serif; background: #F4F4F5; color: #18181B; }
h1 { font-size: 20px; margin: 0 0 8px; }
p { margin: 0 0 12px; max-width: 72ch; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid #D4D4D8; padding: 6px 8px; text-align: left; vertical-align: middle; }
th { position: sticky; top: 0; background: #E4E4E7; }
td.light { background: #FFFFFF; }
td.dark { background: #1C1C1F; }
td img { width: 48px; height: 48px; object-fit: contain; }
code { font-size: 12px; word-break: break-all; }
.warn { color: #B91C1C; }
"""


def page(title: str, intro: str, body: str) -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html.escape(title)}</title>\n<style>{PAGE_STYLE}</style>\n</head>\n<body>\n"
        f"<h1>{html.escape(title)}</h1>\n<p>{intro}</p>\n{body}</body>\n</html>\n"
    )


def review(root: Path) -> list:
    """Write the review sheets. Returns their repository-relative paths, index first."""
    colours = load_colours(root)
    index = load_index(root)
    source = repo_path(root, BITMAP_CACHE)
    if not source.is_file():
        raise BrandingError(f"{BITMAP_CACHE} not found: the dark map cannot be simulated")
    upstream_text = source.read_bytes().decode("utf-8")
    before_maps = parse_colour_maps(upstream_text)
    after_maps = parse_colour_maps(branded_source(upstream_text, colours))
    out_dir = repo_path(root, REVIEW_DIR)
    empty_in_place(out_dir)
    written = []
    links = []
    for group in CANDIDATE_GROUPS:
        entries = [entry for entry in index["candidates"] if entry["group"] == group]
        if not entries:
            continue
        rows = []
        for entry in entries:
            path = entry["path"]
            before = repo_path(root, path).read_bytes().decode("utf-8", "surrogateescape")
            after = candidate_path(root, path).read_bytes().decode("utf-8", "surrogateescape")
            cells = []
            for mode in ("light", "dark"):
                for label, text, maps in (("before", before, before_maps), ("after", after, after_maps)):
                    alt = html.escape(f"{path} {label} {mode}")
                    cells.append(f'<td class="{mode}"><img alt="{alt}" src="{data_uri(apply_map(text, maps[mode]))}"></td>')
            changes = ", ".join(f"{colour} x{count}" for colour, count in entry["replacements"].items())
            left = ""
            if entry["teal_left"]:
                left = f'<br><span class="warn">teal left: {html.escape(", ".join(entry["teal_left"]))}</span>'
            rows.append(
                f"<tr><td><code>{html.escape(path)}</code><br>{html.escape(changes)}{left}</td>{''.join(cells)}</tr>\n"
            )
        header = (
            "<table>\n<tr><th>File</th><th>Before, light</th><th>After, light</th>"
            "<th>Before, dark</th><th>After, dark</th></tr>\n"
        )
        intro = (
            f"{len(entries)} candidate(s). Light cells: {BACKGROUNDS['light']} with the light colour map of "
            f"<code>{BITMAP_CACHE}</code>. Dark cells: {BACKGROUNDS['dark']} with its dark map, branded as the build "
            "brands it. Accept with <code>just brand-accept &lt;group or glob&gt;</code>."
        )
        name = f"{group}.html"
        write_text(out_dir / name, page(f"SVG candidates: {group}", intro, header + "".join(rows) + "</table>\n"))
        written.append(f"{REVIEW_DIR}/{name}")
        links.append(f'<li><a href="{name}">{html.escape(group)}</a>: {len(entries)} candidate(s)</li>')
    notes = []
    if index["unlisted"]:
        notes.append(f'<p class="warn">{len(index["unlisted"])} teal SVG(s) without a manifest row were skipped (just brand-sync).</p>')
    if index["unchanged"]:
        listed = ", ".join(f"{entry['path']} ({', '.join(entry['teal_left'])})" for entry in index["unchanged"])
        notes.append(f"<p>{len(index['unchanged'])} row(s) have no validated mapping to apply and no candidate: {html.escape(listed)}</p>")
    body = "<ul>\n" + "\n".join(links) + "\n</ul>\n" + "\n".join(notes) + "\n"
    write_text(out_dir / "index.html", page("SVG candidates", "One sheet per manifest group.", body))
    return [f"{REVIEW_DIR}/index.html", *written]


# ---------------------------------------------------------------- accept


def select_entries(index: dict, pattern: str) -> list:
    if pattern in CANDIDATE_GROUPS:
        return [entry for entry in index["candidates"] if entry["group"] == pattern]
    return [entry for entry in index["candidates"] if fnmatch.fnmatchcase(entry["path"], pattern)]


def accept(root: Path, pattern: str) -> list:
    """Copy the matching candidates into the overlay as `to-validate` rows.

    All or nothing: every selected candidate is checked (current colours.json,
    unchanged upstream file, unedited candidate, a `missing` row) before any
    file is written. Returns the accepted paths.
    """
    refuse_when_branded(root)
    index = load_index(root)
    chosen = select_entries(index, pattern)
    if not chosen:
        raise BrandingError(f"no candidate matches {pattern!r}")
    current_colours = colours_sha(root)
    if index["colours_sha256"] != current_colours:
        raise BrandingError(f"{COLOURS_FILE} changed since the candidates were made; run `just brand-candidates` again")
    current = manifest_module.load(root)
    rows = current.by_path()
    problems = []
    for entry in chosen:
        path = entry["path"]
        group, row = rows.get(path, (None, None))
        candidate = candidate_path(root, path)
        upstream = repo_path(root, path)
        if row is None:
            problems.append(f"{path}: no manifest row (just brand-sync)")
        elif row["status"] != "missing":
            problems.append(f"{path}: the row is {row['status']}; refresh it before replacing its overlay")
        elif not upstream.is_file() or file_sha256(upstream) != entry["upstream_sha256"] or row["upstream_sha256"] != entry["upstream_sha256"]:
            problems.append(f"{path}: the upstream file changed; run `just brand-sync` and `just brand-candidates`")
        elif not candidate.is_file() or file_sha256(candidate) != entry["candidate_sha256"]:
            problems.append(f"{path}: the candidate file is missing or was edited; run `just brand-candidates`")
    if problems:
        raise BrandingError("; ".join(problems))
    source_ref = f"just brand-candidates, colours.json sha256 {current_colours[:12]}"
    accepted = []
    for entry in chosen:
        path = entry["path"]
        target = manifest_module.overlay_path(root, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidate_path(root, path), target)
        _, row = rows[path]
        row.update(source="candidate", source_ref=source_ref, status="to-validate", override_sha256=file_sha256(target))
        accepted.append(path)
    manifest_module.save(root, current)
    render.write(root, manifest_module.load(root))
    return accepted


# ---------------------------------------------------------------- command line

REPO_ROOT = Path(__file__).resolve().parents[3]


def main(argv=None, root: Path = REPO_ROOT, out=print) -> int:
    parser = argparse.ArgumentParser(prog="candidates.py", description="Cosmyx SVG recolour candidates")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("generate", help=f"write the candidates under {CANDIDATES_DIR}/")
    commands.add_parser("review", help=f"write the HTML review sheets under {REVIEW_DIR}/")
    acceptor = commands.add_parser("accept", help="copy candidates into the overlay as to-validate rows")
    acceptor.add_argument("pattern", help="a group name (icons-a-m, icons-n-z, web) or a glob on the path")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            for line in generate_report(generate(root)):
                out(line)
        elif args.command == "review":
            written = review(root)
            out(f"Review sheet: {repo_path(root, written[0])}")
            for path in written[1:]:
                out(f"  {path}")
        else:
            accepted = accept(root, args.pattern)
            for path in accepted:
                out(f"accepted {path}")
            out(f"Accepted {len(accepted)} candidate(s) as to-validate; commit the overlay, manifest and tables.")
        return 0
    except (BrandingError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
