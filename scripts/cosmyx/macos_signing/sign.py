"""codesign every Mach-O file and bundle of an app, inside out, then the app
(decision 0152). Never `--deep`: it is deprecated and cannot sign the
relocated Python runtime, so each nested file is signed explicitly with the
hardened runtime, a secure timestamp and the shared entitlements
(scripts/disable_validation.entitlements, the same file upstream signs with).
"""

from __future__ import annotations

from pathlib import Path

from . import Context, chunks
from .discover import Item, plan

BATCH = 200


def codesign_args(ctx: Context, extra: list[str] | None = None) -> list[str]:
    settings = ctx.settings
    args = ["codesign", "--force", "--options", "runtime"]
    args.append("--timestamp=none" if settings.adhoc else "--timestamp")
    args += ["--entitlements", str(settings.entitlements), "--sign", settings.identity]
    if settings.keychain and not settings.adhoc:
        args += ["--keychain", settings.keychain]
    return args + (extra or [])


def sign_items(ctx: Context, items: list[Item]) -> None:
    """Sign in the given order; consecutive files share one codesign call."""
    index = 0
    while index < len(items):
        if items[index].kind == "bundle":
            ctx.must(codesign_args(ctx) + [str(items[index].path)], f"codesign {items[index].path.name}")
            index += 1
            continue
        end = index
        while end < len(items) and items[end].kind == "macho":
            end += 1
        for batch in chunks(items[index:end], BATCH):
            ctx.must(codesign_args(ctx) + [str(item.path) for item in batch], "codesign of Mach-O files")
        index = end


def sign_app(ctx: Context, app: Path) -> int:
    """Sign one app; returns how many Mach-O files were signed."""
    items, objects = plan(app)
    machos = sum(1 for item in items if item.kind == "macho")
    bundles = len(items) - machos
    ctx.say(f"signing {app.name}: {machos} Mach-O files, {bundles} bundles (the app last)")
    for path in objects:
        ctx.say(f"  left unsigned (object file, not loadable code): {path.relative_to(app).as_posix()}")
    sign_items(ctx, items)
    ctx.must(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app)], f"codesign --verify {app.name}")
    return machos


def sign_file(ctx: Context, path: Path) -> None:
    """Sign a disk image: a timestamped signature, no runtime or entitlements (they apply to code)."""
    args = ["codesign", "--force", "--sign", ctx.settings.identity]
    args.append("--timestamp=none" if ctx.settings.adhoc else "--timestamp")
    if ctx.settings.keychain and not ctx.settings.adhoc:
        args += ["--keychain", ctx.settings.keychain]
    ctx.must(args + [str(path)], f"codesign {path.name}")
