"""The branding image tables: `cosmyx-src/branding/manifest/<group>.json`.

Each file is `{"schema": 1, "group": "<group>", "rows": [...]}` with rows
sorted by path. A row describes one upstream file the Cosmyx build replaces:

- `path`: repository-relative POSIX path of the upstream file.
- `format`: `svg`, `png`, `ico`, `icns` or `gif` (the path's extension).
- `size`: pixel size (`64x64`, `16,32,48` for an ICO, `multi` for an ICNS).
- `usage`: where the file shows, for the reviewer.
- `kind`: `logo` (a new image) or `recolour` (the same icon in Cosmyx colours).
- `source`: `cosmoslice`, `candidate`, `derived`, `user`, or null while missing.
- `source_ref`: commit, recipe or note the override comes from, or null.
- `status`: `missing` (no override yet), `to-validate`, `validated`.
- `upstream_sha256`: hash of the upstream file the row was checked against
  (null when upstream has no such file).
- `override_sha256`: hash of `overlay/<path>`, null while missing.

A row is `missing` if and only if it has no overlay file and a null
`override_sha256`. Hashes are taken over LF bytes for SVG, raw bytes otherwise.

Groups: `logos` holds the branding images (found by LOGO_PATTERNS), `web` the
teal SVGs under resources/web, `icons-a-m` and `icons-n-z` the teal SVGs under
resources/images split on the first letter of the path below that folder.
"""

from __future__ import annotations

import fnmatch
import re
import struct
from dataclasses import dataclass
from pathlib import Path

from . import (
    DEFAULT_IGNORE,
    GROUPS,
    MANIFEST_DIR,
    OVERLAY_DIR,
    BrandingError,
    check_relative,
    dump_json,
    file_format,
    file_sha256,
    find_hexes,
    in_family,
    load_json,
    relative_posix,
    repo_path,
    same_text,
    write_text,
)

SCHEMA = 1
FIELDS = (
    "path",
    "format",
    "size",
    "usage",
    "kind",
    "source",
    "source_ref",
    "status",
    "upstream_sha256",
    "override_sha256",
)
FORMATS = ("svg", "png", "ico", "icns", "gif")
KINDS = ("logo", "recolour")
SOURCES = ("cosmoslice", "candidate", "derived", "user")
STATUSES = ("missing", "to-validate", "validated")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")

# Branding images, found by name so that a new upstream variant (for example
# another OrcaSlicer_* size) gets its row on the next sync.
LOGO_PATTERNS = (
    "resources/Icon.icns",
    "resources/images/OrcaSlicer*",
    "resources/images/splash_logo*",
    "resources/images/studio_logo*",
    "resources/images/stl.icns",
    "resources/images/gcode.icns",
    "resources/web/image/logo*",
    "scripts/msix/assets/*",
)
TEAL_ROOTS = ("resources/images", "resources/web")
DEFAULT_USAGE = {"logos": "branding image", "web": "web UI image", "icons-a-m": "icon", "icons-n-z": "icon"}


# ---------------------------------------------------------------- rows


def new_row(path: str, **values) -> dict:
    row = {field: None for field in FIELDS}
    row.update(path=path, format=file_format(path), size="", usage="", status="missing")
    row.update(values)
    return {field: row[field] for field in FIELDS}


def is_logo_path(path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in LOGO_PATTERNS) and file_format(path) in FORMATS


def group_for(path: str) -> str:
    """The group a new row goes to."""
    if is_logo_path(path):
        return "logos"
    if path.startswith("resources/web/"):
        return "web"
    if path.startswith("resources/images/"):
        first = path[len("resources/images/") :][:1].lower()
        return "icons-n-z" if "n" <= first <= "z" else "icons-a-m"
    return "logos"


def group_allows(group: str, path: str) -> bool:
    """Whether `path` may live in `group` (rows are never moved by sync)."""
    if group == "logos":
        return True
    return group_for(path) == group


# ---------------------------------------------------------------- tables


@dataclass
class Manifest:
    """Every group's rows, keyed by group name."""

    groups: dict

    def rows(self):
        for group in GROUPS:
            for row in self.groups.get(group, []):
                yield group, row

    def by_path(self) -> dict:
        return {row["path"]: (group, row) for group, row in self.rows()}

    def count(self) -> dict:
        return {group: len(self.groups.get(group, [])) for group in GROUPS}


def manifest_file(root: Path, group: str) -> Path:
    return repo_path(root, f"{MANIFEST_DIR}/{group}.json")


def serialise(group: str, rows: list) -> str:
    ordered = sorted(rows, key=lambda row: row["path"])
    return dump_json({"schema": SCHEMA, "group": group, "rows": [{f: r[f] for f in FIELDS} for r in ordered]})


def load(root: Path) -> Manifest:
    """Read every group file. A missing file is an empty group."""
    groups = {}
    for group in GROUPS:
        path = manifest_file(root, group)
        if not path.is_file():
            groups[group] = []
            continue
        data = load_json(path)
        if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
            raise BrandingError(f"{path}: expected an object with a 'rows' list")
        groups[group] = data["rows"]
    return Manifest(groups)


def save(root: Path, manifest: Manifest) -> None:
    for group in GROUPS:
        write_text(manifest_file(root, group), serialise(group, manifest.groups.get(group, [])))


def validate(root: Path, manifest: Manifest | None = None) -> list[str]:
    """Problems with the tables themselves (schema, order, canonical form).

    Returns human-readable messages; empty when the tables are sound.
    """
    problems = []
    seen = {}
    for group in GROUPS:
        path = manifest_file(root, group)
        if not path.is_file():
            problems.append(f"{MANIFEST_DIR}/{group}.json is missing")
            continue
        try:
            data = load_json(path)
        except BrandingError as error:
            problems.append(str(error))
            continue
        if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("group") != group:
            problems.append(f"{group}.json: expected schema {SCHEMA} and group {group!r}")
            continue
        rows = data.get("rows")
        if not isinstance(rows, list):
            problems.append(f"{group}.json: 'rows' must be a list")
            continue
        own = []
        for row in rows:
            own.extend(f"{group}.json: {message}" for message in validate_row(group, row))
            if isinstance(row, dict) and isinstance(row.get("path"), str):
                if row["path"] in seen:
                    own.append(f"{row['path']} is listed in {seen[row['path']]} and {group}")
                seen[row["path"]] = group
        paths = [row.get("path") for row in rows if isinstance(row, dict)]
        if paths != sorted(paths, key=str):
            own.append(f"{group}.json: rows are not sorted by path")
        if not own and not same_text(path, serialise(group, rows)):
            own.append(f"{group}.json is not in canonical form (run `just brand-sync`)")
        problems.extend(own)
    return problems


def validate_row(group: str, row) -> list[str]:
    if not isinstance(row, dict):
        return [f"row is not an object: {row!r}"]
    if tuple(row.keys()) != FIELDS:
        return [f"{row.get('path')!r}: fields must be exactly {', '.join(FIELDS)} in that order"]
    problems = []
    path = row["path"]
    try:
        check_relative(path)
    except BrandingError as error:
        return [str(error)]
    if row["format"] not in FORMATS or row["format"] != file_format(path):
        problems.append(f"{path}: format must be the extension, one of {', '.join(FORMATS)}")
    if row["kind"] not in KINDS:
        problems.append(f"{path}: kind must be one of {', '.join(KINDS)}")
    if row["status"] not in STATUSES:
        problems.append(f"{path}: status must be one of {', '.join(STATUSES)}")
    if row["source"] is not None and row["source"] not in SOURCES:
        problems.append(f"{path}: source must be null or one of {', '.join(SOURCES)}")
    for key in ("size", "usage"):
        if not isinstance(row[key], str):
            problems.append(f"{path}: {key} must be a string")
    if row["source_ref"] is not None and not isinstance(row["source_ref"], str):
        problems.append(f"{path}: source_ref must be null or a string")
    for key in ("upstream_sha256", "override_sha256"):
        value = row[key]
        if value is not None and not (isinstance(value, str) and SHA_RE.match(value)):
            problems.append(f"{path}: {key} must be null or 64 lowercase hex digits")
    if (row["status"] == "missing") != (row["override_sha256"] is None):
        problems.append(f"{path}: status 'missing' if and only if override_sha256 is null")
    if not group_allows(group, path):
        problems.append(f"{path}: belongs to group {group_for(path)}, not {group}")
    return problems


# ---------------------------------------------------------------- discovery


def walk_files(root: Path, top: str):
    base = repo_path(root, top)
    if not base.is_dir():
        return
    for path in sorted(base.rglob("*")):
        if path.is_file():
            yield relative_posix(root, path)


def is_teal_svg(path: Path, family: dict | None = None, ignore=DEFAULT_IGNORE) -> bool:
    try:
        text = path.read_bytes().decode("utf-8", "replace")
    except OSError:
        return False
    return any(in_family(colour, family, ignore) for colour in find_hexes(text))


def discover(root: Path, family: dict | None = None, ignore=DEFAULT_IGNORE) -> dict:
    """Upstream files that need a row: {path: group}."""
    found = {}
    for top in TEAL_ROOTS:
        for path in walk_files(root, top):
            if path.lower().endswith(".svg") and is_teal_svg(repo_path(root, path), family, ignore):
                found[path] = group_for(path)
    # Logo patterns are shallow: only the folders they name are listed.
    for folder in sorted({pattern.rsplit("/", 1)[0] for pattern in LOGO_PATTERNS}):
        directory = repo_path(root, folder)
        if not directory.is_dir():
            continue
        for entry in sorted(directory.iterdir()):
            relative = relative_posix(root, entry)
            if entry.is_file() and is_logo_path(relative):
                found[relative] = "logos"
    return found


def overlay_files(root: Path) -> list[str]:
    """Repository-relative paths that have an overlay file (`.gitkeep` excluded)."""
    base = repo_path(root, OVERLAY_DIR)
    if not base.is_dir():
        return []
    result = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.name != ".gitkeep":
            result.append(relative_posix(base, path))
    return result


def overlay_path(root: Path, path: str) -> Path:
    return repo_path(root, f"{OVERLAY_DIR}/{path}")


# ---------------------------------------------------------------- image sizes


def _png_size(data: bytes) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return f"{width}x{height}"
    return ""


def _gif_size(data: bytes) -> str:
    if data[:4] == b"GIF8" and len(data) >= 10:
        width, height = struct.unpack("<HH", data[6:10])
        return f"{width}x{height}"
    return ""


def _ico_size(data: bytes) -> str:
    if len(data) < 6 or data[:4] != b"\x00\x00\x01\x00":
        return ""
    (count,) = struct.unpack("<H", data[4:6])
    sizes = []
    for index in range(count):
        entry = data[6 + 16 * index : 22 + 16 * index]
        if len(entry) < 16:
            break
        sizes.append(entry[0] or 256)
    return ",".join(str(size) for size in sorted(set(sizes)))


def _svg_size(data: bytes) -> str:
    text = data[:4096].decode("utf-8", "replace")
    tag = re.search(r"<svg\b[^>]*>", text, re.DOTALL)
    if not tag:
        return ""
    view_box = re.search(r"viewBox\s*=\s*[\"']([^\"']+)[\"']", tag.group(0))
    if view_box:
        parts = view_box.group(1).replace(",", " ").split()
        if len(parts) == 4:
            return f"{_number(parts[2])}x{_number(parts[3])}"
    width = re.search(r"\bwidth\s*=\s*[\"']([0-9.]+)", tag.group(0))
    height = re.search(r"\bheight\s*=\s*[\"']([0-9.]+)", tag.group(0))
    if width and height:
        return f"{_number(width.group(1))}x{_number(height.group(1))}"
    return ""


def _number(text: str) -> str:
    try:
        value = float(text)
    except ValueError:
        return text
    return str(int(value)) if value == int(value) else f"{value:g}"


def image_size(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError:
        return ""
    fmt = file_format(path.name)
    if fmt == "png":
        return _png_size(data)
    if fmt == "gif":
        return _gif_size(data)
    if fmt == "ico":
        return _ico_size(data)
    if fmt == "icns":
        return "multi"
    if fmt == "svg":
        return _svg_size(data)
    return ""


# ---------------------------------------------------------------- sync / refresh / validate


def _upstream_facts(root: Path, path: str) -> tuple:
    upstream = repo_path(root, path)
    if upstream.is_file():
        return file_sha256(upstream), image_size(upstream)
    overlay = overlay_path(root, path)
    return None, image_size(overlay) if overlay.is_file() else ""


def sync(root: Path, family: dict | None = None, ignore=DEFAULT_IGNORE) -> dict:
    """Bring the tables in line with the (un-branded) tree. Returns counts.

    - adds a `missing` row for every discovered file without one;
    - adds a `to-validate` row (source `user`) for an overlay file without one;
    - on a row with no override yet, refreshes `upstream_sha256` and `size`, and
      drops it when the upstream file is gone or no longer needs a row;
    - records the hash of a newly added overlay file (status `to-validate`);
    - never touches a row that already has an override: an upstream change
      under it is guard G3's, and `refresh` re-baselines it.
    """
    manifest = load(root)
    discovered = discover(root, family, ignore)
    overlays = set(overlay_files(root))
    stats = {"added": 0, "dropped": 0, "updated": 0}
    result = {group: [] for group in GROUPS}
    known = set()
    for group, row in manifest.rows():
        path = row["path"]
        known.add(path)
        has_overlay = path in overlays
        if row["override_sha256"] is None and not has_overlay:
            upstream = repo_path(root, path)
            if not upstream.is_file() or path not in discovered:
                stats["dropped"] += 1
                continue
            sha, size = _upstream_facts(root, path)
            if (sha, size) != (row["upstream_sha256"], row["size"]):
                stats["updated"] += 1
            row = dict(row, upstream_sha256=sha, size=size, status="missing", format=file_format(path))
        elif row["override_sha256"] is None and has_overlay:
            row = dict(
                row,
                override_sha256=file_sha256(overlay_path(root, path)),
                status="to-validate",
                source=row["source"] or "user",
            )
            stats["updated"] += 1
        result[group].append(row)
    for path in sorted((set(discovered) | overlays) - known):
        group = discovered.get(path) or group_for(path)
        sha, size = _upstream_facts(root, path)
        values = dict(
            size=size,
            usage=DEFAULT_USAGE[group],
            kind="logo" if group == "logos" else "recolour",
            upstream_sha256=sha,
        )
        if path in overlays:
            values.update(source="user", status="to-validate", override_sha256=file_sha256(overlay_path(root, path)))
        try:
            result[group].append(new_row(check_relative(path), **values))
        except BrandingError:
            continue
        stats["added"] += 1
    save(root, Manifest(result))
    stats.update(load(root).count())
    return stats


def select(manifest: Manifest, pattern: str) -> list:
    """Rows matching `pattern`: a group name, or an fnmatch glob on the path."""
    if pattern in GROUPS:
        return [(group, row) for group, row in manifest.rows() if group == pattern]
    return [(group, row) for group, row in manifest.rows() if fnmatch.fnmatchcase(row["path"], pattern)]


def refresh(root: Path, pattern: str) -> list[str]:
    """Re-baseline the matching rows after an upstream or overlay change.

    Both hashes are recomputed; a row with an overlay goes back to
    `to-validate` (the user reviews it again), one without is `missing`.
    """
    manifest = load(root)
    chosen = select(manifest, pattern)
    if not chosen:
        raise BrandingError(f"no manifest row matches {pattern!r}")
    for group, row in chosen:
        path = row["path"]
        sha, size = _upstream_facts(root, path)
        overlay = overlay_path(root, path)
        override = file_sha256(overlay) if overlay.is_file() else None
        row.update(
            upstream_sha256=sha,
            size=size or row["size"],
            override_sha256=override,
            status="to-validate" if override else "missing",
        )
    save(root, manifest)
    return [row["path"] for _, row in chosen]


def mark_validated(root: Path, pattern: str) -> list[str]:
    """Set the matching `to-validate` rows to `validated`. Only the user calls this."""
    manifest = load(root)
    chosen = select(manifest, pattern)
    if not chosen:
        raise BrandingError(f"no manifest row matches {pattern!r}")
    changed = []
    for _, row in chosen:
        if row["status"] != "to-validate":
            continue
        overlay = overlay_path(root, row["path"])
        if not overlay.is_file() or file_sha256(overlay) != row["override_sha256"]:
            raise BrandingError(f"{row['path']}: overlay is absent or differs from its recorded hash; refresh it first")
        row["status"] = "validated"
        changed.append(row["path"])
    save(root, manifest)
    return changed


def pending(manifest: Manifest, pattern: str) -> list[str]:
    return [row["path"] for _, row in select(manifest, pattern) if row["status"] == "to-validate"]
