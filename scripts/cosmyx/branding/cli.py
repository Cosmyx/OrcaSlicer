"""Command line of the Cosmyx branding engine.

    python scripts/cosmyx/branding/cli.py <command> [options]

Commands:

- `check`: run the guards on the tree (pre-guards, or post-guards when the
  tree is branded) and the review-table check, writing nothing.
- `apply [--ci]`: brand the tree (see apply.py). `--ci` prints GitHub
  annotations and writes the step summary.
- `revert`: restore every file the last apply wrote, byte for byte.
- `sync`: bring the manifest in line with the tree, then the review tables.
- `refresh PATTERN`: re-baseline the matching rows after an upstream or
  overlay change (rows with an overlay go back to `to-validate`).
- `validate PATTERN --i-am-the-user`: mark the matching `to-validate` rows
  `validated`. Only the user runs it, by hand, in a terminal: it refuses
  without the flag (or COSMYX_BRAND_VALIDATOR set), without a terminal, in CI,
  and without the typed confirmation. Agents never run it.
- `render [--check]`: write the review tables, or check they are up to date.
- `mode`: print the branding mode this environment selects (`strict` or
  `tolerant`, see `brand_mode`); the cosmyx-prepare action exports it.

`check` and `apply` take `--mode strict|tolerant` to override the detected
mode (COSMYX_BRAND_MODE). Strict is the default.

PATTERN is a group name (`logos`, `icons-a-m`, `icons-n-z`, `web`) or an
fnmatch glob on the repository-relative path.

Exit codes: 0 done, 1 guard failure or refusal, 2 usage or table error.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in (None, ""):
    # Run as a script: make the package importable from scripts/cosmyx.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from branding import MODE_ENV, MODES, BrandingError, brand_mode, errors, manifest, render  # noqa: E402
from branding import apply as apply_module  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIRMATION = "validate"


def refuse_when_branded(root: Path) -> None:
    if apply_module.State(root).active:
        raise BrandingError("the tree is branded; run `just brand-revert` first")


def mode_env(mode: str | None) -> dict | None:
    """The environment apply and check read: this process's, with the mode
    forced when `--mode` is given."""
    return None if mode is None else {**os.environ, MODE_ENV: mode}


def cmd_check(root: Path, out, mode: str | None = None) -> int:
    findings = apply_module.check(root, mode_env(mode))
    for finding in findings:
        out(str(finding))
    failed = errors(findings)
    out(f"Branding check: {len(failed)} error(s), {len(findings) - len(failed)} warning(s).")
    return 1 if failed else 0


def cmd_sync(root: Path, out) -> int:
    refuse_when_branded(root)
    stats = manifest.sync(root)
    render.write(root, manifest.load(root))
    counts = ", ".join(f"{group} {stats[group]}" for group in manifest.GROUPS)
    out(f"Synced: {stats['added']} added, {stats['updated']} updated, {stats['dropped']} dropped; rows {counts}.")
    return 0


def cmd_refresh(root: Path, pattern: str, out) -> int:
    refuse_when_branded(root)
    paths = manifest.refresh(root, pattern)
    render.write(root, manifest.load(root))
    for path in paths:
        out(f"refreshed {path}")
    return 0


def validator_refusal(flag: bool, env: dict, isatty) -> str | None:
    """Why `validate` must not run, or None when a human may run it."""
    if not (flag or env.get("COSMYX_BRAND_VALIDATOR")):
        return "validate is for the user only: pass --i-am-the-user (agents must never run it)"
    if env.get("CI") or env.get("GITHUB_ACTIONS"):
        return "validate never runs in CI"
    if not isatty():
        return "validate needs an interactive terminal"
    return None


def cmd_validate(root: Path, pattern: str, flag: bool, out, env=None, isatty=None, ask=input) -> int:
    env = os.environ if env is None else env
    isatty = isatty or (lambda: sys.stdin.isatty() and sys.stdout.isatty())
    refusal = validator_refusal(flag, env, isatty)
    if refusal:
        out(f"refused: {refusal}")
        return 1
    refuse_when_branded(root)
    rows = manifest.pending(manifest.load(root), pattern)
    if not rows:
        out(f"No to-validate row matches {pattern!r}.")
        return 0
    for path in rows:
        out(f"  {path}")
    answer = ask(f"Mark these {len(rows)} row(s) validated? Type '{CONFIRMATION}' to confirm: ")
    if answer.strip() != CONFIRMATION:
        out("refused: not confirmed")
        return 1
    changed = manifest.mark_validated(root, pattern)
    render.write(root, manifest.load(root))
    out(f"Validated {len(changed)} row(s).")
    return 0


def cmd_render(root: Path, check: bool, out) -> int:
    current = manifest.load(root)
    if check:
        stale = render.stale(root, current)
        for path in stale:
            out(f"out of date: {path} (just brand-table)")
        return 1 if stale else 0
    for path in render.write(root, current):
        out(f"wrote {path}")
    return 0


def main(argv: list[str] | None = None, out=print) -> int:
    parser = argparse.ArgumentParser(description="Apply, check and maintain the Cosmyx branding.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this checkout)")
    sub = parser.add_subparsers(dest="command", required=True)
    checker = sub.add_parser("check", help="run the guards, writing nothing")
    applier = sub.add_parser("apply", help="brand the tree")
    applier.add_argument("--ci", action="store_true", help="GitHub annotations and step summary")
    for command in (checker, applier):
        command.add_argument("--mode", choices=MODES, help="override the detected mode (default: strict)")
    sub.add_parser("mode", help="print the branding mode this environment selects")
    sub.add_parser("revert", help="undo the last apply exactly")
    sub.add_parser("sync", help="bring the manifest and the review tables in line with the tree")
    refresher = sub.add_parser("refresh", help="re-baseline rows after an upstream or overlay change")
    refresher.add_argument("pattern")
    validator = sub.add_parser("validate", help="USER ONLY: mark to-validate rows validated")
    validator.add_argument("pattern")
    validator.add_argument("--i-am-the-user", dest="i_am_the_user", action="store_true")
    renderer = sub.add_parser("render", help="write or check the review tables")
    renderer.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.resolve()

    try:
        if args.command == "check":
            return cmd_check(root, out, args.mode)
        if args.command == "apply":
            return apply_module.apply(root, ci=args.ci, env=mode_env(args.mode), out=out)
        if args.command == "mode":
            out(brand_mode(root=root))
            return 0
        if args.command == "revert":
            restored = apply_module.revert(root)
            out(f"Reverted {len(restored)} file(s).")
            return 0
        if args.command == "sync":
            return cmd_sync(root, out)
        if args.command == "refresh":
            return cmd_refresh(root, args.pattern, out)
        if args.command == "validate":
            return cmd_validate(root, args.pattern, args.i_am_the_user, out)
        return cmd_render(root, args.check, out)
    except (BrandingError, OSError) as error:
        out(f"error: {error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
