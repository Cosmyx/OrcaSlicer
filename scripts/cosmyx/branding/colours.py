"""Colour stage of the Cosmyx branding engine (T11c): Orca teal -> Cosmyx violet.

The engine (apply.py) applies the `literals` rows of colours.json with
`textpatch` first, then calls this plugin, which:

1. applies the `snippets` rows (a line inserted after an exact anchor, with an
   exact count), and
2. rewrites every `#RRGGBB` (any case, 8-digit keeps its alpha) whose colour
   is the `from` of a `mappings` row, in the files matched by `scopes`. The
   rewrite is explicit: only mapped colours change, always to uppercase, and
   never inside an `href`, a `url(...)` reference, a URL fragment, a
   numeric character reference (`&#NNNNNN;`) or base64 data.

The teal family recogniser never rewrites anything; it only finds leftovers.
Hex leftovers are reported by guard G5 of the engine; this plugin adds the
leftovers the engine cannot see (colour tuples such as `wxColour(0, 150, 136)`
or `ImVec4(0.00f, 0.59f, 0.53f, 1.0f)`, `0xRRGGBB` integers, and mapped
colours outside the family), each allowed only by an exact `allow_residue`
row. Contrast (WCAG 2.x) of every mapping pair on #FFFFFF and #1C1C1F goes in
the report; it informs the user's review and never fails a build.

Command line (writes nothing unless `--write` is given):

    python scripts/cosmyx/branding/colours.py candidates
    python scripts/cosmyx/branding/colours.py literals [--write]

`candidates` prints the mapping table with its contrast and the blends the
derived roles come from. `literals` prints the tuple literal rows the tree
needs today (rows whose reason starts with `tuple `); `--write` replaces them
in colours.json and keeps every hand-written row.

Removing this file turns the colour stage into literal rows only: the engine
still loads colours.json, but no hex is rewritten and no tuple leftover is
caught.
"""

from __future__ import annotations

if __package__ in (None, ""):
    # Run as a script: import this module through its package.
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from branding.colours import main

    raise SystemExit(main())

import argparse
import re
import sys
from pathlib import Path

from . import (
    COLOURS_FILE,
    HEX_LOOKBACK,
    BrandingError,
    Finding,
    dump_json,
    find_hexes,
    hex_is_skipped,
    in_family,
    load_json,
    read_lf,
    repo_path,
    write_text,
)
from . import textpatch
from .guards import scope_files

SOURCES = ("user", "derived")
STATUSES = ("to-validate", "validated")
BACKGROUNDS = ("#FFFFFF", "#1C1C1F")
CANONICAL_HEX_RE = re.compile(r"^#[0-9A-F]{6}$")
TUPLE_REASON = "tuple "
# Float colour components are rounded from 0..1 values: accept this much
# difference per channel when matching a tuple against a mapped colour.
FLOAT_TOLERANCE = 2

# ---------------------------------------------------------------- hex rewrite

HEX_BYTES_RE = re.compile(rb"#([0-9A-Fa-f]{6})((?:[0-9A-Fa-f]{2})?)(?![0-9A-Fa-f])")
_BASE64_BYTES_RE = re.compile(rb"base64,[A-Za-z0-9+/=\s]+")


def rewrite_hex(data: bytes, table: dict) -> tuple:
    """Rewrite the mapped `#RRGGBB` colours of `data`.

    `table` maps uppercase `#RRGGBB` to uppercase `#RRGGBB`. Returns the new
    bytes and {from: count}. Works on bytes, so any ASCII-compatible encoding
    and any line ending is kept as it is.
    """
    protected = [match.span() for match in _BASE64_BYTES_RE.finditer(data)]
    counts: dict = {}

    def replace(match: re.Match) -> bytes:
        start = match.start()
        if any(low <= start < high for low, high in protected):
            return match.group(0)
        if hex_is_skipped(data[max(0, start - HEX_LOOKBACK) : start].decode("latin-1")):
            return match.group(0)
        colour = "#" + match.group(1).decode("ascii").upper()
        target = table.get(colour)
        if target is None:
            return match.group(0)
        counts[colour] = counts.get(colour, 0) + 1
        return target.encode("ascii") + match.group(2)

    return HEX_BYTES_RE.sub(replace, data), counts


# ---------------------------------------------------------------- tuples

_NUMBER = r"(?:0[xX][0-9A-Fa-f]{1,2}|\d+\.?\d*(?:[eE][-+]?\d+)?[fF]?|\.\d+[fF]?)(?:\s*/\s*255(?:\.\d*)?[fF]?)?"
TUPLE_RE = re.compile(
    r"(?P<head>\b(?:wxColour|wxColor|IM_COL32|ImColor|ImVec4|ColorRGBA|ColorRGB|rgba|rgb)\s*\(\s*"
    r"|(?:=|\breturn|\()\s*\{\s*)"
    rf"(?P<c1>{_NUMBER})(?P<s1>\s*,\s*)(?P<c2>{_NUMBER})(?P<s2>\s*,\s*)(?P<c3>{_NUMBER})"
    r"(?![0-9A-Za-z.])"
)
INT_HEX_RE = re.compile(r"\b0[xX]([0-9A-Fa-f]{6})\b")
_COMPONENT_RE = re.compile(r"^(?P<num>[^\s/]+)(?P<rest>\s*/\s*255.*)?$", re.DOTALL)


def _component(text: str):
    """(kind, value) of one tuple component: kind is hex, ratio, float or int."""
    match = _COMPONENT_RE.match(text)
    number, rest = match.group("num"), match.group("rest")
    if number.lower().startswith("0x"):
        return ("hex", int(number, 16)) if not rest else (None, None)
    value = float(number.rstrip("fF"))
    if rest:
        return "ratio", value
    if any(char in number for char in ".eEfF"):
        return "float", value
    return "int", value


# Constructors that only take 0..1 floats: their integer components are 0 or 1.
FLOAT_HEADS = ("ImVec4", "ColorRGB")


def tuple_rgb(components: list, head: str = ""):
    """(r, g, b, normalised) of three component texts, or None if not a colour."""
    parsed = [_component(text) for text in components]
    if any(kind is None for kind, _ in parsed):
        return None
    normalised = head.lstrip().startswith(FLOAT_HEADS) or any(kind == "float" for kind, _ in parsed)
    rgb = []
    for kind, value in parsed:
        if kind in ("hex", "ratio") or (kind == "int" and not normalised):
            channel = value
        elif kind == "int" and value not in (0, 1):
            return None
        else:
            channel = value * 255.0
        if not 0 <= channel <= 255.5:
            return None
        rgb.append(int(round(channel)))
    return rgb[0], rgb[1], rgb[2], normalised


def hex_of(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb[:3])


def rgb_of(colour: str) -> tuple:
    return tuple(int(colour[i : i + 2], 16) for i in (1, 3, 5))


def find_tuples(text: str):
    """Yield (match, (r, g, b, normalised)) for every colour tuple in `text`."""
    for match in TUPLE_RE.finditer(text):
        rgb = tuple_rgb([match.group("c1"), match.group("c2"), match.group("c3")], match.group("head"))
        if rgb is not None:
            yield match, rgb


def _format_component(text: str, channel: int, lower_hex: bool = False) -> str:
    """`text` rewritten to carry `channel` (0..255), in the same notation.
    `lower_hex` writes hex digits in lowercase, as the tuple they come from."""
    match = _COMPONENT_RE.match(text)
    number, rest = match.group("num"), match.group("rest") or ""
    kind, _ = _component(text)
    if kind == "hex":
        digits = f"{channel:02X}"
        return number[:2] + (digits.lower() if lower_hex else digits)
    if kind == "ratio":
        parts = re.match(r"^(\d*)(\.\d*)?([fF]?)$", number)
        if parts is None:
            return f"{channel}{rest}"
        fraction = parts.group(2) or ""
        if len(fraction) > 1:
            fraction = "." + "0" * (len(fraction) - 1)
        return f"{channel}{fraction}{parts.group(3)}{rest}"
    if kind == "float" or kind == "int":
        # A float tuple: keep the decimals of the original (at least 3 when it
        # had none) and its `f` suffix.
        suffix = "f" if number.endswith(("f", "F")) else ""
        fraction = number.rstrip("fF").partition(".")[2]
        decimals = len(fraction) if len(fraction) >= 2 else 3
        return f"{channel / 255.0:.{decimals}f}{suffix}"
    return text


def rewrite_tuple(match: re.Match, target: str, normalised: bool) -> str:
    """The matched tuple text with its three components carrying `target`."""
    values = rgb_of(target)
    components = [match.group(name) for name in ("c1", "c2", "c3")]
    lower_hex = any(char in "abcdef" for component in components for char in component[2:])
    pieces = [match.group("head")]
    for index, name in enumerate(("c1", "c2", "c3")):
        component = match.group(name)
        kind, _ = _component(component)
        if kind == "int" and not normalised:
            pieces.append(str(values[index]))
        else:
            pieces.append(_format_component(component, values[index], lower_hex))
        if index < 2:
            pieces.append(match.group(f"s{index + 1}"))
    return "".join(pieces)


def close_to(rgb, colour: str, tolerance: int) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(rgb[:3], rgb_of(colour)))


def mapped_colour(rgb, table: dict):
    """The mapping source a tuple stands for, or None."""
    tolerance = FLOAT_TOLERANCE if rgb[3] else 0
    for source in table:
        if close_to(rgb, source, tolerance):
            return source
    return None


# ---------------------------------------------------------------- WCAG


def luminance(colour: str) -> float:
    """WCAG 2.x relative luminance of `#RRGGBB`."""

    def linear(channel: int) -> float:
        value = channel / 255.0
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (linear(channel) for channel in rgb_of(colour))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: str, second: str) -> float:
    """WCAG 2.x contrast ratio, from 1.0 to 21.0, rounded to two decimals."""
    high, low = sorted((luminance(first), luminance(second)), reverse=True)
    return round((high + 0.05) / (low + 0.05), 2)


def blend(foreground: str, background: str, alpha: float) -> str:
    """`foreground` at `alpha` opacity over `background`, rounded per channel."""
    mixed = (
        int(round(back + alpha * (fore - back))) for fore, back in zip(rgb_of(foreground), rgb_of(background))
    )
    return hex_of(tuple(mixed))


def contrast_rows(colours: dict) -> list:
    rows = []
    for row in colours.get("mappings", []):
        entry = {"from": row["from"], "to": row["to"], "role": row.get("role", "")}
        for background in BACKGROUNDS:
            entry[f"from_on_{background[1:]}"] = contrast(row["from"], background)
            entry[f"to_on_{background[1:]}"] = contrast(row["to"], background)
        rows.append(entry)
    return rows


# ---------------------------------------------------------------- table


def table_problems(colours: dict) -> list:
    """Everything wrong with the colour-specific parts of colours.json."""
    problems = []
    palette = colours.get("palette") or {}
    if not isinstance(palette, (dict, list)):
        problems.append(f"palette: must be an object or a list, got {palette!r}")
        palette = {}
    palette_items = list(palette.items() if isinstance(palette, dict) else enumerate(palette))
    # Guard G7 greps every palette value as a case-insensitive substring of the
    # tracked files: only a full uppercase #RRGGBB is a safe needle.
    for name, value in palette_items:
        if not isinstance(value, str) or not CANONICAL_HEX_RE.match(value):
            problems.append(f"palette[{name!r}]: must be an uppercase #RRGGBB, got {value!r}")
    palette_values = {value for _, value in palette_items if isinstance(value, str)}
    ignore = {str(item).upper() for item in colours.get("ignore") or ()}
    seen = set()
    for index, row in enumerate(colours.get("mappings", [])):
        where = f"mappings[{index}]"
        if not isinstance(row, dict):
            problems.append(f"{where}: not an object")
            continue
        for key in ("from", "to"):
            value = row.get(key)
            if not isinstance(value, str) or not CANONICAL_HEX_RE.match(value):
                problems.append(f"{where}: {key} must be an uppercase #RRGGBB, got {value!r}")
        if not isinstance(row.get("role"), str) or not row.get("role"):
            problems.append(f"{where}: role must be given")
        if row.get("source") not in SOURCES:
            problems.append(f"{where}: source must be one of {', '.join(SOURCES)}")
        if row.get("status") not in STATUSES:
            problems.append(f"{where}: status must be one of {', '.join(STATUSES)}")
        source = row.get("from")
        if source in seen:
            problems.append(f"{where}: {source} is mapped twice")
        seen.add(source)
        if isinstance(source, str) and source.upper() in ignore:
            problems.append(f"{where}: {source} is in ignore")
        if isinstance(row.get("to"), str) and palette_values and row["to"] not in palette_values:
            problems.append(f"{where}: {row['to']} is not a palette colour")
    for index, row in enumerate(colours.get("snippets", [])):
        try:
            snippet_patch(row)
        except BrandingError as error:
            problems.append(f"snippets[{index}]: {error}")
    for index, row in enumerate(colours.get("allow_residue", [])):
        if not isinstance(row, dict) or not all(key in row for key in ("file", "match", "count", "reason")):
            problems.append(f"allow_residue[{index}]: needs file, match, count, reason")
    return problems


def mapping_table(colours: dict) -> dict:
    return {
        row["from"]: row["to"]
        for row in colours.get("mappings", [])
        if isinstance(row, dict) and isinstance(row.get("from"), str) and isinstance(row.get("to"), str)
    }


def snippet_patch(row: dict) -> textpatch.Patch:
    """A snippet row `{file, anchor, insert, count, reason}` as a text patch:
    `insert` becomes a new line right after every occurrence of `anchor`."""
    if not isinstance(row, dict):
        raise BrandingError(f"snippet row is not an object: {row!r}")
    missing = [key for key in ("file", "anchor", "insert", "count", "reason") if key not in row]
    if missing:
        raise BrandingError(f"snippet row {row!r} lacks {', '.join(missing)}")
    if not isinstance(row["insert"], str) or not row["insert"] or "\n" in row["insert"]:
        raise BrandingError(f"snippet row {row!r}: insert must be one non-empty line")
    return textpatch.normalise(
        {
            "file": row["file"],
            "find": row["anchor"],
            "replace": f"{row['anchor']}\n{row['insert']}",
            "count": row["count"],
            "reason": row["reason"],
        }
    )


def snippet_patches(colours: dict) -> list:
    return [snippet_patch(row) for row in colours.get("snippets", [])]


# ---------------------------------------------------------------- scans


def scope_paths(ctx) -> list:
    return scope_files(ctx.root, (ctx.colours or {}).get("scopes", []))


def read_scope_text(root: Path, relative: str) -> str:
    """A scope file's text with LF line endings, so a literal row spanning a
    line break has the same text and count on a CRLF (Windows) checkout."""
    return read_lf(repo_path(root, relative), "replace")


def tuple_key(rgb) -> str:
    return "rgb({}, {}, {})".format(*rgb[:3])


def leftovers(root: Path, files: list, colours: dict, family: dict, ignore) -> dict:
    """{(file, MATCH): count} the engine's hex scan cannot see.

    MATCH is `RGB(R, G, B)` for a colour tuple, `0XRRGGBB` for an integer
    literal (both in the teal family or mapped), or `#RRGGBB` for a mapped
    hex colour outside the family.
    """
    table = mapping_table(colours)
    found: dict = {}

    def add(relative: str, key: str) -> None:
        found[(relative, key.upper())] = found.get((relative, key.upper()), 0) + 1

    for relative in files:
        text = read_scope_text(root, relative)
        for _, rgb in find_tuples(text):
            if in_family(hex_of(rgb), family, ignore) or mapped_colour(rgb, table):
                add(relative, tuple_key(rgb))
        for match in INT_HEX_RE.finditer(text):
            colour = "#" + match.group(1).upper()
            if in_family(colour, family, ignore) or colour in table:
                add(relative, "0x" + match.group(1))
        for colour in find_hexes(text):
            if colour in table and not in_family(colour, family, ignore):
                add(relative, colour)
    return found


def propose_literals(root: Path, colours: dict) -> list:
    """The tuple and integer literal rows the tree needs for the mapped colours.

    One row per file and exact text, its count the occurrences of that text.
    """
    table = mapping_table(colours)
    rows = []
    for relative in scope_files(root, colours.get("scopes", [])):
        text = read_scope_text(root, relative)
        texts: dict = {}
        for match, rgb in find_tuples(text):
            source = mapped_colour(rgb, table)
            if source is None:
                continue
            texts[match.group(0)] = (rewrite_tuple(match, table[source], rgb[3]), source)
        for match in INT_HEX_RE.finditer(text):
            source = "#" + match.group(1).upper()
            if source in table:
                digits = table[source][1:]
                digits = digits.lower() if match.group(1).islower() else digits
                texts[match.group(0)] = (match.group(0)[:2] + digits, source)
        for find, (replace, source) in sorted(texts.items()):
            rows.append(
                {
                    "file": relative,
                    "find": find,
                    "replace": replace,
                    "count": text.count(find),
                    "reason": f"{TUPLE_REASON}{source} -> {table[source]}",
                }
            )
    return rows


# ---------------------------------------------------------------- plugin


def apply(ctx, backup) -> dict:
    """Snippets, then the explicit hex rewrite over the scopes."""
    colours = ctx.colours or {}
    snippets = textpatch.apply(ctx.root, snippet_patches(colours), backup)
    table = mapping_table(colours)
    totals: dict = {}
    files = 0
    for relative in scope_paths(ctx):
        path = repo_path(ctx.root, relative)
        data = path.read_bytes()
        new, counts = rewrite_hex(data, table)
        if not counts:
            continue
        backup(relative)
        path.write_bytes(new)
        files += 1
        for colour, count in counts.items():
            totals[colour] = totals.get(colour, 0) + count
    return {
        "snippets": snippets,
        "rewritten_files": files,
        "replacements": dict(sorted(totals.items())),
        "contrast": contrast_rows(colours),
    }


def guards(ctx, phase: str) -> list:
    colours = ctx.colours
    if not colours:
        return []
    findings = [Finding("G5", "error", COLOURS_FILE, problem) for problem in table_problems(colours)]
    if findings:
        return findings
    if phase == "pre":
        findings += [
            Finding("G5", "error", "", message)
            for message in textpatch.mismatches(ctx.root, snippet_patches(colours))
        ]
        pending = [row for row in colours.get("mappings", []) if row["status"] != "validated"]
        if pending:
            level = "error" if ctx.kind == "release" else "warning"
            findings.append(
                Finding("P", level, COLOURS_FILE, f"{len(pending)} colour mapping(s) to-validate; release builds need all validated")
            )
        return findings
    family, ignore = ctx.family()
    permits = {
        (row["file"], str(row["match"]).upper()): int(row["count"]) for row in colours.get("allow_residue", [])
    }
    for (relative, key), count in sorted(leftovers(ctx.root, scope_paths(ctx), colours, family, ignore).items()):
        if permits.get((relative, key)) != count:
            findings.append(Finding("G5", "error", relative, f"teal {key} left {count} time(s) after apply"))
    for row in colours.get("snippets", []):
        if read_scope_text(ctx.root, row["file"]).count(row["insert"]) != row["count"]:
            findings.append(Finding("G5", "error", row["file"], "snippet not in place after apply"))
    return findings


# ---------------------------------------------------------------- command line

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_colours(root: Path) -> dict:
    path = repo_path(root, COLOURS_FILE)
    if not path.is_file():
        raise BrandingError(f"{COLOURS_FILE} not found")
    data = load_json(path)
    problems = table_problems(data)
    if problems:
        raise BrandingError("; ".join(problems))
    return data


def candidates_text(colours: dict) -> str:
    """The mapping table with contrast, then the blends of each derived role."""
    palette = colours.get("palette") or {}
    lines = ["Mappings (contrast on #FFFFFF / #1C1C1F):", ""]
    lines.append(f"{'from':8}  {'to':8}  {'role':42}  {'source':7}  {'status':11}  from W/D       to W/D")
    for row, entry in zip(colours.get("mappings", []), contrast_rows(colours)):
        lines.append(
            f"{row['from']:8}  {row['to']:8}  {row['role']:42}  {row['source']:7}  {row['status']:11}  "
            f"{entry['from_on_FFFFFF']:5.2f} {entry['from_on_1C1C1F']:5.2f}    "
            f"{entry['to_on_FFFFFF']:5.2f} {entry['to_on_1C1C1F']:5.2f}"
        )
    brand = palette.get("brand", "#8000FF")
    screen = palette.get("brand_dark_screen", "#A472F5")
    lines += ["", "Blends (candidate, contrast on #FFFFFF / #1C1C1F):", ""]
    blends = [
        (f"{brand} 25% over #FFFFFF (light tint 25)", brand, "#FFFFFF", 0.25),
        (f"{brand} 10% over #FFFFFF (light tint 10)", brand, "#FFFFFF", 0.10),
        (f"{screen} 25% over #2D2D31 (dark tint 25)", screen, "#2D2D31", 0.25),
        (f"{screen} 10% over #2D2D31 (dark tint 10)", screen, "#2D2D31", 0.10),
        (f"{brand} 25% over #1C1C1F (dark tint 25, screen bg)", brand, "#1C1C1F", 0.25),
    ]
    blends += [(f"{brand} lightened {int(step * 100)}% (hover)", "#FFFFFF", brand, step) for step in (0.15, 0.25, 0.35)]
    blends += [(f"{brand} darkened {int(step * 100)}% (pressed)", "#000000", brand, step) for step in (0.15, 0.25)]
    for label, foreground, background, alpha in blends:
        colour = blend(foreground, background, alpha)
        lines.append(f"{colour}  {contrast(colour, '#FFFFFF'):5.2f} {contrast(colour, '#1C1C1F'):5.2f}  {label}")
    lines += ["", "Text on brand fills:", ""]
    for fill in sorted({row["to"] for row in colours.get("mappings", [])}):
        lines.append(f"#FFFFFF on {fill}: {contrast('#FFFFFF', fill):5.2f}   #000000 on {fill}: {contrast('#000000', fill):5.2f}")
    return "\n".join(lines) + "\n"


def wiki_table(colours: dict) -> str:
    """The Markdown table of the mappings and their contrast, as in
    wiki/cosmyx/branding.md (the status lives in colours.json only)."""
    lines = [
        "| From | To | Role | Source | From on white / dark | To on white / dark |",
        "|------|----|------|--------|----------------------|--------------------|",
    ]
    for row, entry in zip(colours.get("mappings", []), contrast_rows(colours)):
        lines.append(
            f"| `{row['from']}` | `{row['to']}` | {row['role']} | {row['source']} | "
            f"{entry['from_on_FFFFFF']:.2f} / {entry['from_on_1C1C1F']:.2f} | "
            f"{entry['to_on_FFFFFF']:.2f} / {entry['to_on_1C1C1F']:.2f} |"
        )
    return "\n".join(lines) + "\n"


def literal_rows(root: Path, colours: dict) -> list:
    """Hand-written literal rows kept, tuple rows regenerated from the tree."""
    kept = [row for row in colours.get("literals", []) if not str(row.get("reason", "")).startswith(TUPLE_REASON)]
    return kept + propose_literals(root, colours)


def main(argv=None, root: Path = REPO_ROOT, out=print) -> int:
    parser = argparse.ArgumentParser(prog="colours.py", description="Cosmyx colour tools")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("candidates", help="print the mappings with their contrast and the candidate blends")
    literals = commands.add_parser("literals", help="print the tuple literal rows the tree needs")
    literals.add_argument("--write", action="store_true", help="write them into colours.json")
    args = parser.parse_args(argv)
    try:
        colours = load_colours(root)
        if args.command == "candidates":
            out(candidates_text(colours) + "\nWiki table (wiki/cosmyx/branding.md):\n\n" + wiki_table(colours).rstrip("\n"))
            return 0
        rows = literal_rows(root, colours)
        if args.write:
            write_text(repo_path(root, COLOURS_FILE), dump_json(dict(colours, literals=rows)))
            out(f"{COLOURS_FILE}: {len(rows)} literal row(s)")
        else:
            out(dump_json(rows).rstrip("\n"))
        return 0
    except BrandingError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
