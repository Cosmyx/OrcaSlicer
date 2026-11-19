"""Apply and revert the Cosmyx branding on a checked-out tree.

Apply order (frozen contract): pre-guards, overlay, colours, product name,
post-guards, then the report (`build/cosmyx/branding-report.json`, and the
GitHub step summary with `--ci`).

- Nothing is written when a pre-guard fails.
- Every file is backed up under `build/cosmyx/branding-state/` before its
  first write, so `revert` restores the exact bytes (and deletes the files
  the overlay created). A stage or post-guard failure reverts at once.
- Applying an applied tree reverts it first, so apply is idempotent.

Stages:

- overlay: `overlay.apply` (manifest rows with an override).
- colours: active when `colours.json` exists. Its `literals` rows are applied
  with `textpatch`, then the optional plugin `colours.py` (T11c) runs.
- product name: active when `product-name/*.json` exists. The `patches` rows
  are applied with `textpatch`, then the optional plugin `product_name/`
  (T11e) runs.

A plugin is a module of this package exposing
`apply(ctx, backup) -> dict` (it calls `backup(path)` before writing any file
and returns what goes in the report) and `guards(ctx, phase) -> list[Finding]`.
"""

from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from . import (
    COLOURS_FILE,
    DEFAULT_FAMILY,
    DEFAULT_IGNORE,
    GROUPS,
    PRODUCT_NAME_DIR,
    REPORT_FILE,
    STATE_DIR,
    BrandingError,
    Finding,
    dump_json,
    errors,
    load_json,
    ref_kind,
    repo_path,
    write_text,
)
from . import guards, overlay, textpatch
from . import manifest as manifest_module

PACKAGE_DIR = Path(__file__).resolve().parent
PRODUCT_NAME_TABLES = ("rename", "allowlist", "patches")
PLUGINS = {"colours": "colours", "product_name": "product_name"}


class Context:
    """Everything a stage or a guard reads: the tree, the tables, the policy."""

    def __init__(self, root: Path, env: dict | None = None, plugins: dict | None = None):
        self.root = root
        self.kind = ref_kind(env)
        self.manifest = manifest_module.load(root)
        self.table_problems: list = []
        self.colours = self._load_colours()
        self.product_name = self._load_product_name()
        self.plugins = load_plugins() if plugins is None else plugins
        self.snapshot: dict = {}

    def _load_colours(self):
        path = repo_path(self.root, COLOURS_FILE)
        if not path.is_file():
            return None
        try:
            data = load_json(path)
        except BrandingError as error:
            self.table_problems.append((COLOURS_FILE, str(error)))
            return {}
        if not isinstance(data, dict):
            self.table_problems.append((COLOURS_FILE, "must be a JSON object"))
            return {}
        return data

    def _load_product_name(self):
        tables = {}
        present = False
        for name in PRODUCT_NAME_TABLES:
            relative = f"{PRODUCT_NAME_DIR}/{name}.json"
            path = repo_path(self.root, relative)
            tables[name] = []
            if not path.is_file():
                continue
            present = True
            try:
                data = load_json(path)
            except BrandingError as error:
                self.table_problems.append((relative, str(error)))
                continue
            if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("rows"), list):
                self.table_problems.append((relative, 'expected {"schema": 1, "rows": [...]}'))
                continue
            tables[name] = data["rows"]
        return tables if present else None

    def family(self):
        colours = self.colours or {}
        return colours.get("family") or DEFAULT_FAMILY, tuple(colours.get("ignore") or DEFAULT_IGNORE)


def load_plugins() -> dict:
    """The optional stage modules present in this package."""
    found = {}
    for key, name in PLUGINS.items():
        if (PACKAGE_DIR / f"{name}.py").is_file() or (PACKAGE_DIR / name / "__init__.py").is_file():
            found[key] = [importlib.import_module(f"{__package__}.{name}")]
        else:
            found[key] = []
    return found


# ---------------------------------------------------------------- state


class State:
    """Backups of every file the branding wrote, for an exact revert."""

    def __init__(self, root: Path):
        self.root = root
        self.dir = repo_path(root, STATE_DIR)
        self.file = self.dir / "state.json"
        self.files: dict = {}
        if self.file.is_file():
            self.files = load_json(self.file).get("files", {})

    @property
    def active(self) -> bool:
        return self.file.is_file()

    def backup_path(self, relative: str) -> Path:
        return self.dir.joinpath("backup", *relative.split("/"))

    def save(self) -> None:
        write_text(self.file, dump_json({"schema": 1, "files": dict(sorted(self.files.items()))}))

    def backup(self, relative: str) -> None:
        if relative in self.files:
            return
        source = repo_path(self.root, relative)
        created = not source.exists()
        if not created:
            destination = self.backup_path(relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        self.files[relative] = {"created": created}
        self.save()

    def restore(self) -> list[str]:
        restored = []
        for relative, entry in sorted(self.files.items()):
            target = repo_path(self.root, relative)
            if entry.get("created"):
                if target.exists():
                    target.unlink()
            else:
                shutil.copy2(self.backup_path(relative), target)
                self.backup_path(relative).unlink()
            restored.append(relative)
        clear_skip_worktree(self.root, restored)
        # The folders are emptied, never removed: on a network share a folder
        # removed and recreated at once can fail.
        if self.file.is_file():
            self.file.unlink()
        self.files = {}
        return restored


def clear_skip_worktree(root: Path, paths: list) -> None:
    """Drop the skip-worktree bit the CI hide step may have set on `paths`.

    Outside a git checkout, or for files git does not track, nothing happens.
    """
    wanted = {path.encode("utf-8") for path in paths}
    listing = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-v", "-z"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False
    )
    if listing.returncode != 0:
        return
    hidden = [entry[2:] for entry in listing.stdout.split(b"\0") if entry.startswith(b"S ") and entry[2:] in wanted]
    if hidden:
        subprocess.run(
            ["git", "-C", str(root), "update-index", "--no-skip-worktree", "-z", "--stdin"],
            input=b"\0".join(hidden) + b"\0",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


# ---------------------------------------------------------------- stages


def stage_overlay(ctx: Context, state: State) -> dict:
    return {"written": overlay.apply(ctx.root, ctx.manifest, state.backup)}


def stage_colours(ctx: Context, state: State) -> dict:
    if ctx.colours is None:
        return {"active": False}
    literals = [textpatch.normalise(row) for row in ctx.colours.get("literals", [])]
    report = {"active": True, "literals": textpatch.apply(ctx.root, literals, state.backup)}
    for plugin in ctx.plugins.get("colours", []):
        report["plugin"] = plugin.apply(ctx, state.backup)
    return report


def stage_product_name(ctx: Context, state: State) -> dict:
    if ctx.product_name is None:
        return {"active": False}
    patches = [textpatch.normalise(row) for row in ctx.product_name.get("patches", [])]
    report = {"active": True, "patches": textpatch.apply(ctx.root, patches, state.backup)}
    for plugin in ctx.plugins.get("product_name", []):
        report["plugin"] = plugin.apply(ctx, state.backup)
    return report


STAGES = (("overlay", stage_overlay), ("colours", stage_colours), ("product_name", stage_product_name))


# ---------------------------------------------------------------- pipeline


def status_counts(ctx: Context) -> dict:
    return {
        group: {
            status: sum(1 for row in ctx.manifest.groups.get(group, []) if row["status"] == status)
            for status in manifest_module.STATUSES
        }
        for group in GROUPS
    }


def apply(root: Path, ci: bool = False, env: dict | None = None, out=print, plugins: dict | None = None) -> int:
    """Brand the tree. Returns 0 when applied, 1 when refused or failed."""
    state = State(root)
    if state.active:
        state.restore()
    ctx = Context(root, env, plugins)
    findings = guards.run(ctx, "pre")
    stages: dict = {}
    result = "applied"
    if errors(findings):
        result = "refused"
    else:
        try:
            for name, stage in STAGES:
                stages[name] = stage(ctx, state)
        except (BrandingError, OSError) as error:
            findings.append(Finding("apply", "error", "", str(error)))
            result = "failed"
        if result == "applied":
            findings += guards.run(ctx, "post")
            if errors(findings):
                result = "failed"
        if result == "failed":
            state.restore()
    write_report(root, ctx, result, stages, findings, ci, env, out)
    return 0 if result == "applied" else 1


def revert(root: Path) -> list[str]:
    return State(root).restore()


def check(root: Path, env: dict | None = None, plugins: dict | None = None) -> list[Finding]:
    """Guards on the current tree: post-guards when it is branded, else pre."""
    ctx = Context(root, env, plugins)
    return guards.run(ctx, "post" if State(root).active else "pre")


def write_report(root, ctx, result, stages, findings, ci, env, out) -> None:
    report = {
        "schema": 1,
        "result": result,
        "kind": ctx.kind,
        "counts": status_counts(ctx),
        "stages": stages,
        "findings": [finding.as_dict() for finding in findings],
    }
    write_text(repo_path(root, REPORT_FILE), json.dumps(report, indent=2, sort_keys=True) + "\n")
    for finding in findings:
        if ci and finding.level in ("error", "warning"):
            prefix = f"::{finding.level} file={finding.path}::" if "/" in finding.path else f"::{finding.level}::"
            out(f"{prefix}{finding.guard} {finding.path} {finding.message}")
        else:
            out(str(finding))
    out(f"Branding {result} ({ctx.kind} build): {summary_line(report)}")
    environment = os.environ if env is None else env
    summary_file = environment.get("GITHUB_STEP_SUMMARY")
    if ci and summary_file:
        with open(summary_file, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(step_summary(report))


def summary_line(report: dict) -> str:
    written = len(report["stages"].get("overlay", {}).get("written", []))
    errors_count = sum(1 for item in report["findings"] if item["level"] == "error")
    warnings_count = sum(1 for item in report["findings"] if item["level"] == "warning")
    return f"{written} overlay file(s), {errors_count} error(s), {warnings_count} warning(s)"


def step_summary(report: dict) -> str:
    lines = [f"### Cosmyx branding: {report['result']} ({report['kind']} build)", ""]
    lines += ["| Group | Missing | To validate | Validated |", "|---|---|---|---|"]
    for group, counts in report["counts"].items():
        lines.append(f"| {group} | {counts['missing']} | {counts['to-validate']} | {counts['validated']} |")
    lines += ["", summary_line(report), ""]
    for item in report["findings"]:
        lines.append(f"- {item['level']} {item['guard']} `{item['path']}` {item['message']}")
    return "\n".join(lines) + "\n\n"
