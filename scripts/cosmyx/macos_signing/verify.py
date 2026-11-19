"""Verify the signed and notarised result; any problem fails the step (decision 0155).

Per app: `codesign --verify --deep --strict`, then for every Mach-O file a
Developer ID Application authority, our team, the hardened runtime, a secure
timestamp and no get-task-allow entitlement; Gatekeeper (`spctl -t exec`) must
see a notarised Developer ID; the ticket is stapled. Per DMG: stapled, and
`spctl -t open --context context:primary-signature` accepts it. When
`syspolicy_check` exists (macOS 14+), `syspolicy_check distribution` runs too.

An ad-hoc dry run checks only what an ad-hoc signature can have: the deep
verify, the runtime flag, an ad-hoc signature and no get-task-allow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from . import Context, SigningError, tail
from .discover import plan

DEVELOPER_ID = "Developer ID Application:"
NOTARIZED = "source=Notarized Developer ID"
RUNTIME_FLAG = 0x10000


@dataclass
class Signature:
    """What `codesign -d --verbose=4` says about one file."""

    authorities: list[str] = field(default_factory=list)
    team: str = ""
    flags: int = 0
    adhoc: bool = False
    timestamp: bool = False
    signed: bool = True

    @property
    def runtime(self) -> bool:
        return bool(self.flags & RUNTIME_FLAG)


def parse_display(text: str) -> Signature:
    sig = Signature()
    if "not signed at all" in text:
        sig.signed = False
    for line in text.splitlines():
        key, _, value = line.partition("=")
        if key == "Authority":
            sig.authorities.append(value.strip())
        elif key == "TeamIdentifier":
            sig.team = "" if value.strip() == "not set" else value.strip()
        elif key == "Signature" and value.strip() == "adhoc":
            sig.adhoc = True
        elif key == "Timestamp":
            sig.timestamp = True
        elif key == "CodeDirectory v":
            found = re.search(r"flags=0x([0-9a-fA-F]+)", line)
            if found:
                sig.flags = int(found.group(1), 16)
    return sig


def file_problems(sig: Signature, entitlements: str, team: str, adhoc: bool) -> list[str]:
    """Why one file's signature is not acceptable (empty when it is)."""
    if not sig.signed:
        return ["not signed"]
    problems = []
    if adhoc:
        if not sig.adhoc:
            problems.append("not ad-hoc signed")
    else:
        if not sig.authorities or not sig.authorities[0].startswith(DEVELOPER_ID):
            problems.append(f"authority is {sig.authorities[0] if sig.authorities else 'none'}, not {DEVELOPER_ID}")
        if sig.team != team:
            problems.append(f"team {sig.team or 'not set'}, expected the TEAM_ID team")
        if not sig.timestamp:
            problems.append("no secure timestamp")
    if not sig.runtime:
        problems.append("no hardened runtime")
    if "get-task-allow" in entitlements:
        problems.append("has the get-task-allow entitlement")
    return problems


def describe(ctx: Context, path: Path) -> tuple[Signature, str]:
    done = ctx.call(["codesign", "-d", "--verbose=4", "--entitlements", "-", "--xml", str(path)])
    return parse_display((done.stderr or "") + "\n" + ("" if done.returncode == 0 else done.stdout or "")), \
        done.stdout if done.returncode == 0 else ""


def check_gatekeeper(ctx: Context, args: list[str], what: str) -> list[str]:
    done = ctx.call(args)
    text = (done.stderr or "") + (done.stdout or "")
    if done.returncode != 0 or "accepted" not in text or NOTARIZED not in text:
        return [f"{what}: {ctx.redact(tail(done))}"]
    return []


def verify_app(ctx: Context, app: Path) -> list[str]:
    s = ctx.settings
    problems = []
    done = ctx.call(["codesign", "--verify", "--deep", "--strict", "-vvv", str(app)])
    if done.returncode != 0:
        problems.append(f"{app.name}: codesign --verify --deep --strict: {ctx.redact(tail(done))}")
    items, _objects = plan(app)
    for item in items:
        sig, entitlements = describe(ctx, item.path)
        rel = item.path.relative_to(app.parent).as_posix()
        for problem in file_problems(sig, entitlements, s.team_id, s.adhoc):
            problems.append(ctx.redact(f"{rel}: {problem}"))
    if s.adhoc:
        return problems
    problems += check_gatekeeper(ctx, ["spctl", "-a", "-vvv", "-t", "exec", str(app)], f"{app.name}: spctl -t exec")
    problems += stapled(ctx, app)
    if ctx.which("syspolicy_check"):
        done = ctx.call(["syspolicy_check", "distribution", str(app)])
        if done.returncode != 0:
            problems.append(f"{app.name}: syspolicy_check distribution: {ctx.redact(tail(done))}")
    return problems


def stapled(ctx: Context, path: Path) -> list[str]:
    done = ctx.call(["xcrun", "stapler", "validate", str(path)])
    return [] if done.returncode == 0 else [f"{path.name}: stapler validate: {ctx.redact(tail(done))}"]


def verify_dmg(ctx: Context, dmg: Path) -> list[str]:
    if ctx.settings.adhoc:
        return []
    problems = stapled(ctx, dmg)
    problems += check_gatekeeper(ctx, ["spctl", "-a", "-vvv", "-t", "open", "--context", "context:primary-signature",
                                       str(dmg)], f"{dmg.name}: spctl -t open")
    return problems


def verify(ctx: Context, apps: list[Path], dmgs: list[Path]) -> None:
    problems = []
    for app in apps:
        problems += verify_app(ctx, app)
    for dmg in dmgs:
        problems += verify_dmg(ctx, dmg)
    if problems:
        ctx.note(f"Verification found {len(problems)} problem(s):")
        for line in problems[:50]:
            ctx.note(f"- {line}")
        if len(problems) > 50:
            ctx.note(f"- ... and {len(problems) - 50} more")
        raise SigningError(f"verification failed: {len(problems)} problem(s)")
    ctx.note(f"Verified {len(apps)} app(s) and {len(dmgs)} disk image(s).")
