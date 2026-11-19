"""Guards G1-G8 and the status policy, run before (`pre`) and after (`post`) apply.

- G1 overlay hash: every override has its overlay file with the recorded
  hash (pre), and the applied file carries that hash (post).
- G2 no orphan overlay: every overlay file has a manifest row.
- G3 upstream: the upstream file still exists with the recorded hash (pre).
- G4 coverage: every teal SVG under resources/images and resources/web, and
  every branding image, has a row (pre).
- G5 colours: every colours.json literal row matches its exact count (pre);
  no teal colour is left in the colour scopes unless allow-listed with its
  exact count (post). Inactive until colours.json exists.
- G6 tables: the manifest is valid and canonical, the review tables under
  wiki/cosmyx/branding-assets are up to date, the other tables parse.
- G7 upstream stays Orca: no palette colour and no "CosmoSlice" in tracked
  files outside the Cosmyx paths (pre), except allow-listed palette rows.
- G8 product name: every patch row matches its exact count (pre), and the
  lines naming SLIC3R_APP_KEY in the patched files are unchanged (post).
  Inactive until product-name/patches.json exists.
- Status policy: `missing` and `to-validate` rows warn on development builds
  (pull requests, DEV, MIXED, local) and fail release builds (release/*
  branches and tags).

Drift (an upstream change the tables have not caught up with: G3 and G4)
follows the status policy too, so a new upstream icon never breaks a
development build; every other finding is an error everywhere.

Optional stage plugins (`colours`, `product_name`) may expose
`guards(ctx, phase) -> list[Finding]`; G5 and G8 append their findings.
"""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

from . import (
    COLOURS_FILE,
    GROUPS,
    PRODUCT_NAME_DIR,
    Finding,
    BrandingError,
    file_sha256,
    find_hexes,
    in_family,
    is_cosmyx_path,
    relative_posix,
    repo_path,
)
from . import manifest as manifest_module
from . import render, textpatch

PHASES = ("pre", "post")
APP_KEY = "SLIC3R_APP_KEY"


def drift_level(ctx) -> str:
    return "error" if ctx.kind == "release" else "warning"


# ---------------------------------------------------------------- G1 / G2


def g1_overlay_hash(ctx, phase: str) -> list[Finding]:
    findings = []
    for _, row in ctx.manifest.rows():
        expected = row["override_sha256"]
        if not expected:
            continue
        path = row["path"]
        if phase == "pre":
            overlay = manifest_module.overlay_path(ctx.root, path)
            if not overlay.is_file():
                findings.append(Finding("G1", "error", path, "override recorded but the overlay file is missing"))
            elif file_sha256(overlay) != expected:
                findings.append(
                    Finding("G1", "error", path, "overlay differs from override_sha256 (just brand-refresh PATH, then review)")
                )
        else:
            target = repo_path(ctx.root, path)
            if not target.is_file() or file_sha256(target) != expected:
                findings.append(Finding("G1", "error", path, "applied file does not carry the override hash"))
    return findings


def g2_orphan_overlay(ctx, phase: str) -> list[Finding]:
    rows = set(ctx.manifest.by_path())
    return [
        Finding("G2", "error", path, "overlay file has no manifest row (just brand-sync)")
        for path in manifest_module.overlay_files(ctx.root)
        if path not in rows
    ]


# ---------------------------------------------------------------- G3 / G4


def g3_upstream(ctx, phase: str) -> list[Finding]:
    if phase != "pre":
        return []
    level = drift_level(ctx)
    findings = []
    for _, row in ctx.manifest.rows():
        path = row["path"]
        upstream = repo_path(ctx.root, path)
        recorded = row["upstream_sha256"]
        if recorded is None:
            if upstream.is_file():
                findings.append(Finding("G3", level, path, "upstream now has this file (just brand-refresh PATH)"))
            continue
        if not upstream.is_file():
            findings.append(Finding("G3", level, path, "upstream file is gone (just brand-sync or brand-refresh PATH)"))
        elif file_sha256(upstream) != recorded:
            advice = "just brand-refresh PATH, then review" if row["override_sha256"] else "just brand-sync"
            findings.append(Finding("G3", level, path, f"upstream file changed ({advice})"))
    return findings


def g4_coverage(ctx, phase: str) -> list[Finding]:
    if phase != "pre":
        return []
    rows = set(ctx.manifest.by_path())
    family, ignore = ctx.family()
    level = drift_level(ctx)
    return [
        Finding("G4", level, path, f"needs a row in {group} (just brand-sync)")
        for path, group in sorted(manifest_module.discover(ctx.root, family, ignore).items())
        if path not in rows
    ]


# ---------------------------------------------------------------- G5


def scope_files(root: Path, patterns: list) -> list[str]:
    """Files matched by colours.json `scopes`: fnmatch globs, `!` excludes."""
    includes = [pattern for pattern in patterns if not pattern.startswith("!")]
    excludes = [pattern[1:] for pattern in patterns if pattern.startswith("!")]
    found = set()
    for pattern in includes:
        prefix = pattern.split("*", 1)[0].rsplit("/", 1)[0]
        base = repo_path(root, prefix) if prefix else root
        if base.is_file():
            candidates = [base]
        elif base.is_dir():
            candidates = (path for path in base.rglob("*") if path.is_file())
        else:
            continue
        for path in candidates:
            relative = relative_posix(root, path)
            if fnmatch.fnmatchcase(relative, pattern) and not any(fnmatch.fnmatchcase(relative, ex) for ex in excludes):
                found.add(relative)
    return sorted(found)


def colour_literals(ctx) -> list:
    return [textpatch.normalise(row) for row in (ctx.colours or {}).get("literals", [])]


def residue(ctx) -> dict:
    """{(file, colour): count} of teal colours left in the colour scopes."""
    family, ignore = ctx.family()
    result = {}
    for relative in scope_files(ctx.root, (ctx.colours or {}).get("scopes", [])):
        text = repo_path(ctx.root, relative).read_bytes().decode("utf-8", "replace")
        for colour in find_hexes(text):
            if in_family(colour, family, ignore):
                result[(relative, colour)] = result.get((relative, colour), 0) + 1
    return result


def allowed(ctx) -> dict:
    """{(file, match uppercased): count} from colours.json `allow_residue`."""
    return {
        (row["file"], str(row["match"]).upper()): int(row["count"])
        for row in (ctx.colours or {}).get("allow_residue", [])
    }


def g5_colours(ctx, phase: str) -> list[Finding]:
    if ctx.colours is None:
        return []
    findings = []
    if phase == "pre":
        try:
            literals = colour_literals(ctx)
        except BrandingError as error:
            return [Finding("G5", "error", COLOURS_FILE, str(error))]
        findings += [Finding("G5", "error", "", message) for message in textpatch.mismatches(ctx.root, literals)]
    else:
        permits = allowed(ctx)
        for (relative, colour), count in sorted(residue(ctx).items()):
            if permits.get((relative, colour)) != count:
                findings.append(Finding("G5", "error", relative, f"teal {colour} left {count} time(s) after apply"))
    for plugin in ctx.plugins.get("colours", []):
        findings += list(plugin.guards(ctx, phase))
    return findings


# ---------------------------------------------------------------- G6


def g6_tables(ctx, phase: str) -> list[Finding]:
    findings = [Finding("G6", "error", "", problem) for problem in manifest_module.validate(ctx.root)]
    findings += [
        Finding("G6", "error", path, "review table is out of date (just brand-table)")
        for path in render.stale(ctx.root, ctx.manifest)
    ]
    unreadable = {name for name, _ in ctx.table_problems}
    if ctx.colours is not None and COLOURS_FILE not in unreadable and ctx.colours.get("schema") != 1:
        findings.append(Finding("G6", "error", COLOURS_FILE, "schema must be 1"))
    for name, problem in ctx.table_problems:
        findings.append(Finding("G6", "error", name, problem))
    return findings


# ---------------------------------------------------------------- G7


def palette(ctx) -> list[str]:
    value = (ctx.colours or {}).get("palette") or []
    values = value.values() if isinstance(value, dict) else value
    return sorted({str(item).upper() for item in values if isinstance(item, str) and item.startswith("#")})


def git_grep(root: Path, needle: str, ignore_case: bool) -> tuple:
    """({path: count} of `needle` in tracked text files, ""), or (None, git's
    error message) when git cannot search the tree (outside git, or a
    workspace git rejects as owned by another user)."""
    args = ["git", "-C", str(root), "grep", "-I", "-F", "-c", "--full-name"]
    if ignore_case:
        args.append("-i")
    process = subprocess.run([*args, "-e", needle], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if process.returncode not in (0, 1):
        message = process.stderr.decode("utf-8", "replace").strip()
        return None, message or f"exit code {process.returncode}"
    counts = {}
    for line in process.stdout.decode("utf-8", "surrogateescape").splitlines():
        path, _, count = line.rpartition(":")
        counts[path] = int(count)
    return counts, ""


def g7_upstream_stays_orca(ctx, phase: str) -> list[Finding]:
    if phase != "pre":
        return []
    needles = [("CosmoSlice", False)] + [(colour, True) for colour in palette(ctx)]
    permits = allowed(ctx)
    findings = []
    for needle, ignore_case in needles:
        counts, error = git_grep(ctx.root, needle, ignore_case)
        if counts is None:
            return [Finding("G7", "warning", "", f"skipped: git grep failed: {error}")]
        for path, count in sorted(counts.items()):
            if is_cosmyx_path(path) or permits.get((path, needle.upper())) == count:
                continue
            findings.append(Finding("G7", "error", path, f"tracked upstream file contains {needle} {count} time(s)"))
    return findings


# ---------------------------------------------------------------- G8


def name_patches(ctx) -> list:
    return [textpatch.normalise(row) for row in (ctx.product_name or {}).get("patches", [])]


def app_key_lines(root: Path, files) -> dict:
    lines = {}
    for relative in sorted(set(files)):
        path = repo_path(root, relative)
        if path.is_file():
            text = path.read_bytes().decode("utf-8", "replace")
            lines[relative] = [line for line in text.splitlines() if APP_KEY in line]
    return lines


def g8_product_name(ctx, phase: str) -> list[Finding]:
    if ctx.product_name is None:
        return []
    try:
        patches = name_patches(ctx)
    except BrandingError as error:
        return [Finding("G8", "error", PRODUCT_NAME_DIR, str(error))]
    files = [patch.file for patch in patches]
    findings = []
    if phase == "pre":
        findings += [Finding("G8", "error", "", message) for message in textpatch.mismatches(ctx.root, patches)]
        ctx.snapshot["app_key_lines"] = app_key_lines(ctx.root, files)
    else:
        before = ctx.snapshot.get("app_key_lines")
        if before is not None and app_key_lines(ctx.root, files) != before:
            findings.append(Finding("G8", "error", "", f"a line naming {APP_KEY} changed; the app key must stay"))
    for plugin in ctx.plugins.get("product_name", []):
        findings += list(plugin.guards(ctx, phase))
    return findings


# ---------------------------------------------------------------- status policy


def status_policy(ctx, phase: str) -> list[Finding]:
    if phase != "pre":
        return []
    level = drift_level(ctx)
    findings = []
    for group in GROUPS:
        rows = ctx.manifest.groups.get(group, [])
        for status in ("missing", "to-validate"):
            count = sum(1 for row in rows if row["status"] == status)
            if count:
                findings.append(Finding("P", level, group, f"{count} row(s) {status}; release builds need all validated"))
    return findings


GUARDS = (
    g1_overlay_hash,
    g2_orphan_overlay,
    g3_upstream,
    g4_coverage,
    g5_colours,
    g6_tables,
    g7_upstream_stays_orca,
    g8_product_name,
    status_policy,
)


def run(ctx, phase: str) -> list[Finding]:
    if phase not in PHASES:
        raise ValueError(phase)
    findings = []
    for guard in GUARDS:
        findings += guard(ctx, phase)
    return findings

