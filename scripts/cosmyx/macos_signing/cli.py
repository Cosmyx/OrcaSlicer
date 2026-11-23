"""Cosmyx macOS signing, command line (wiki/cosmyx/macos-signing.md).

    cli.py run    --root DIR --version VER [--summary FILE] [--log-dir DIR] [--work DIR]
    cli.py dryrun APP [--keep DIR]
    cli.py status [--repo OWNER/NAME] [--branch DEV] [--limit 5]

`run` is what the cosmyx-sign-macos action calls. It reads its settings from
the environment, never from the command line, so no secret reaches a process
listing of this script:

    COSMYX_MAC_SIGN_IDENTITY   codesign identity ("-" for an ad-hoc dry run)
    COSMYX_MAC_KEYCHAIN        keychain holding the identity (needed to notarise:
                               it holds the notary profile, decision 0159)
    COSMYX_MAC_TEAM_ID         Apple team (notarisation and verification)
    COSMYX_MAC_APPLE_ID        Apple ID of the notarisation account
    COSMYX_MAC_APP_PASSWORD    its app-specific password

`dryrun` signs a copy of APP ad-hoc and verifies it, to try the signing order
on a local build. `status` lists the macOS signing step of the latest
"Build all" runs. The CI runs this with `python -I`, so the file puts
scripts/cosmyx on sys.path itself.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from macos_signing import ADHOC, Context, Settings, SigningError  # noqa: E402
from macos_signing import discover, dmg, notarize, sign, verify  # noqa: E402

STEP_NAME = "Cosmyx sign and notarize macOS"
ENV = {
    "identity": "COSMYX_MAC_SIGN_IDENTITY",
    "keychain": "COSMYX_MAC_KEYCHAIN",
    "team_id": "COSMYX_MAC_TEAM_ID",
    "apple_id": "COSMYX_MAC_APPLE_ID",
    "app_password": "COSMYX_MAC_APP_PASSWORD",
}
NOTARY_ENV = ("team_id", "apple_id", "app_password")


def settings_from_env(env) -> Settings:
    values = {key: env.get(name, "").strip() for key, name in ENV.items()}
    if not values["identity"]:
        raise SigningError(f"{ENV['identity']} is empty: nothing to sign with")
    settings = Settings(**values)
    if not settings.adhoc:
        missing = [ENV[key] for key in NOTARY_ENV if not values[key]]
        if missing:
            raise SigningError(f"notarisation needs {', '.join(missing)}")
    return settings


def run_all(ctx: Context, root: Path, version: str, log_dir: Path | None, work: Path) -> None:
    """Sign, notarise and staple every app, rebuild, sign, notarise and staple
    its DMG, then verify everything."""
    apps = discover.find_apps(root)
    ctx.note(f"Signing {len(apps)} app(s) with "
             + ("an ad-hoc signature (dry run, no notarisation)." if ctx.settings.adhoc else "the Developer ID identity."))
    for app in apps:
        count = sign.sign_app(ctx, app)
        ctx.note(f"Signed `{app.name}`: {count} Mach-O files.")
    if not ctx.settings.adhoc:
        zips = [notarize.zip_app(ctx, app, work) for app in apps]
        notarize.notarize(ctx, zips, log_dir)
        for app in apps:
            notarize.staple(ctx, app)
    dmgs = []
    for app in apps:
        image = dmg.build(ctx, app, root, version)
        sign.sign_file(ctx, image)
        dmgs.append(image)
    if not ctx.settings.adhoc:
        notarize.notarize(ctx, dmgs, log_dir)
        for image in dmgs:
            notarize.staple(ctx, image)
    verify.verify(ctx, apps, dmgs)


def write_summary(ctx: Context, path: str, ok: bool) -> None:
    if not path:
        return
    lines = ["## Cosmyx macOS signing", ""] + ctx.summary + ["", f"**Result: {'signed' if ok else 'failed'}**", ""]
    with open(path, "a", encoding="utf-8", newline="\n") as out:
        out.write("\n".join(lines) + "\n")


def cmd_run(args, env=os.environ, run=subprocess.run) -> int:
    try:
        settings = settings_from_env(env)
    except SigningError as error:
        print(f"::error::{error}")
        return 1
    ctx = Context(settings, run=run)
    work = Path(args.work) if args.work else Path(tempfile.mkdtemp(prefix="cosmyx-notary-"))
    ok = False
    try:
        run_all(ctx, Path(args.root), args.version, Path(args.log_dir) if args.log_dir else None, work)
        ok = True
    except SigningError as error:
        print(f"::error::{ctx.redact(str(error))}")
    finally:
        write_summary(ctx, args.summary, ok)
    return 0 if ok else 1


def cmd_dryrun(args, run=subprocess.run) -> int:
    if sys.platform != "darwin":
        print("mac-sign-dryrun needs macOS (codesign); see wiki/cosmyx/macos-signing.md", file=sys.stderr)
        return 1
    source = Path(args.app)
    if source.suffix != ".app" or not source.is_dir():
        print(f"{source} is not an .app folder", file=sys.stderr)
        return 1
    work = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="cosmyx-mac-dryrun-"))
    work.mkdir(parents=True, exist_ok=True)
    app = work / source.name
    if app.exists():
        shutil.rmtree(app)
    shutil.copytree(source, app, symlinks=True)
    ctx = Context(Settings(identity=ADHOC), run=run)
    try:
        count = sign.sign_app(ctx, app)
        verify.verify(ctx, [app], [])
    except SigningError as error:
        print(f"dry run failed: {error}", file=sys.stderr)
        return 1
    finally:
        if not args.keep:
            shutil.rmtree(work, ignore_errors=True)
    print(f"dry run passed: {count} Mach-O files signed ad-hoc in a copy of {source.name}"
          + (f" (kept in {app})" if args.keep else ""))
    return 0


def cmd_status(args, run=subprocess.run) -> int:
    gh = shutil.which("gh")
    if not gh:
        print("gh (GitHub CLI) is needed", file=sys.stderr)
        return 1

    def api(path: str) -> dict:
        return json.loads(run([gh, "api", path], capture_output=True, text=True, check=True).stdout)

    runs = api(f"repos/{args.repo}/actions/workflows/build_all.yml/runs?branch={args.branch}&per_page={args.limit}")
    for item in runs.get("workflow_runs", []):
        state = "no macOS signing step"
        jobs = api(f"repos/{args.repo}/actions/runs/{item['id']}/jobs?per_page=100")
        for job in jobs.get("jobs", []):
            for step in job.get("steps", []):
                if step.get("name") == STEP_NAME:
                    state = step.get("conclusion") or step.get("status") or "?"
        print(f"{item['id']}  {item.get('created_at', '')}  {item.get('head_sha', '')[:12]}  {state}")
    return 0


def parser() -> argparse.ArgumentParser:
    main = argparse.ArgumentParser(description="Cosmyx macOS signing")
    sub = main.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run", help="sign, notarise and staple the universal build (CI)")
    p.add_argument("--root", required=True, help="the workspace (repository root)")
    p.add_argument("--version", required=True, help="the build version in the DMG names")
    p.add_argument("--summary", default="", help="Markdown file to append the summary to")
    p.add_argument("--log-dir", default="", help="folder for the notary logs")
    p.add_argument("--work", default="", help="folder for the notarisation zips")
    p = sub.add_parser("dryrun", help="sign a copy of an app ad-hoc and verify it (macOS)")
    p.add_argument("app")
    p.add_argument("--keep", default="", help="keep the signed copy in this folder")
    p = sub.add_parser("status", help="the macOS signing step of the latest Build all runs")
    p.add_argument("--repo", default=os.environ.get("COSMYX_REPO", "Cosmyx/OrcaSlicer"))
    p.add_argument("--branch", default="DEV")
    p.add_argument("--limit", type=int, default=5)
    return main


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    return {"run": cmd_run, "dryrun": cmd_dryrun, "status": cmd_status}[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
