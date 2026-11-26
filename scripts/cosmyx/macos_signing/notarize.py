"""Notarise with notarytool and staple the tickets (decisions 0153, 0159).

Every file of a round is submitted first, then waited for, so Apple's queue
works on them together. A tool error (network, service) is retried 3 times;
an answer of Invalid or Rejected is final, never retried, and its log is
saved and summarised. Stapling is retried 5 times: the ticket can take a
moment to reach Apple's CDN.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import Context, SigningError, tail

NETWORK_ATTEMPTS = 3
STAPLE_ATTEMPTS = 5
RETRY_DELAY = 30.0
WAIT_TIMEOUT = "40m"
FINAL_FAILURES = ("Invalid", "Rejected")


@dataclass
class Submission:
    path: Path
    id: str
    status: str = ""


PROFILE = "cosmyx-notary"


def store_profile(ctx: Context) -> str:
    """Save the notary credentials as a profile in the run's temporary keychain.

    notarytool store-credentials prompts for the app-specific password when
    --password is left out; the answer goes to its stdin, so the password is
    never on a command line (decision 0159). The profile dies with the keychain
    in the action's clean-up step."""
    s = ctx.settings
    if not s.keychain:
        raise SigningError("notarisation needs the temporary keychain (COSMYX_MAC_KEYCHAIN) to hold its profile")
    done = ctx.call_with_input(["xcrun", "notarytool", "store-credentials", PROFILE, "--apple-id", s.apple_id,
                                "--team-id", s.team_id, "--keychain", s.keychain, "--no-validate"], s.app_password)
    if done.returncode != 0:
        raise SigningError(ctx.redact(f"notarytool store-credentials failed (exit {done.returncode}): {tail(done)}"))
    ctx.notary_profile = PROFILE
    return PROFILE


def credentials(ctx: Context) -> list[str]:
    """The notarytool options that select the stored profile (stored on first use)."""
    profile = ctx.notary_profile or store_profile(ctx)
    return ["--keychain-profile", profile, "--keychain", ctx.settings.keychain]


def _json(done: subprocess.CompletedProcess) -> dict | None:
    try:
        value = json.loads(done.stdout or "")
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def _retrying(ctx: Context, args: list[str], what: str, accept) -> dict:
    """Run a notarytool call until accept(answer) holds or the attempts run out.

    accept returns True (done), False (tool error, retry) or raises (final)."""
    last = ""
    for attempt in range(1, NETWORK_ATTEMPTS + 1):
        done = ctx.call(args)
        answer = _json(done) or {}
        if accept(done, answer):
            return answer
        last = tail(done)
        if attempt < NETWORK_ATTEMPTS:
            ctx.say(f"{what}: attempt {attempt} failed ({ctx.redact(last)}), retrying")
            ctx.sleep(RETRY_DELAY)
    raise SigningError(ctx.redact(f"{what} failed after {NETWORK_ATTEMPTS} attempts: {last}"))


def submit(ctx: Context, path: Path) -> Submission:
    args = ["xcrun", "notarytool", "submit", str(path), *credentials(ctx), "--output-format", "json", "--no-wait"]
    answer = _retrying(ctx, args, f"notarytool submit {path.name}",
                       lambda done, answer: done.returncode == 0 and bool(answer.get("id")))
    ctx.say(f"submitted {path.name}: {answer['id']}")
    return Submission(path, str(answer["id"]))


def fetch_log(ctx: Context, item: Submission, log_dir: Path | None) -> list[str]:
    """Save the notary log, return its issues as summary lines."""
    done = ctx.call(["xcrun", "notarytool", "log", item.id, *credentials(ctx)])
    if done.returncode != 0:
        return [f"  (no notary log: {ctx.redact(tail(done))})"]
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f"{item.path.name}.notary-log.json").write_text(ctx.redact(done.stdout), encoding="utf-8",
                                                                   newline="\n")
    try:
        issues = json.loads(done.stdout).get("issues") or []
    except (ValueError, AttributeError):
        return ["  (notary log is not JSON)"]
    lines = []
    for issue in issues[:20]:
        lines.append(f"  - {issue.get('path', '?')}: {issue.get('message', '?')}")
    if len(issues) > 20:
        lines.append(f"  - ... and {len(issues) - 20} more (see the notary log artifact)")
    return lines


def wait(ctx: Context, item: Submission, log_dir: Path | None) -> None:
    args = ["xcrun", "notarytool", "wait", item.id, *credentials(ctx), "--timeout", WAIT_TIMEOUT,
            "--output-format", "json"]

    def accept(done, answer) -> bool:
        status = answer.get("status", "")
        if status in FINAL_FAILURES:
            item.status = status
            raise _Final(status)
        return done.returncode == 0 and status == "Accepted"

    try:
        _retrying(ctx, args, f"notarytool wait {item.path.name}", accept)
    except _Final as final:
        ctx.note(f"Notarisation of `{item.path.name}` was **{final.status}** (submission {item.id}):")
        for line in fetch_log(ctx, item, log_dir):
            ctx.note(line)
        raise SigningError(f"notarisation of {item.path.name} was {final.status}") from None
    except SigningError:
        ctx.note(f"Notarisation of `{item.path.name}` did not finish (submission {item.id}).")
        fetch_log(ctx, item, log_dir)
        raise
    item.status = "Accepted"
    ctx.note(f"Notarised `{item.path.name}`: Accepted (submission {item.id}).")


class _Final(Exception):
    def __init__(self, status: str) -> None:
        super().__init__(status)
        self.status = status


def notarize(ctx: Context, paths: list[Path], log_dir: Path | None) -> list[Submission]:
    """Submit every file, then wait for each one; any refusal fails the run."""
    submissions = [submit(ctx, path) for path in paths]
    for item in submissions:
        wait(ctx, item, log_dir)
    return submissions


def staple(ctx: Context, path: Path) -> None:
    last = ""
    for attempt in range(1, STAPLE_ATTEMPTS + 1):
        done = ctx.call(["xcrun", "stapler", "staple", str(path)])
        if done.returncode == 0:
            ctx.say(f"stapled {path.name}")
            return
        last = tail(done)
        if attempt < STAPLE_ATTEMPTS:
            ctx.say(f"stapler staple {path.name}: attempt {attempt} failed ({ctx.redact(last)}), retrying")
            ctx.sleep(RETRY_DELAY)
    raise SigningError(ctx.redact(f"stapler staple {path.name} failed after {STAPLE_ATTEMPTS} attempts: {last}"))


def zip_app(ctx: Context, app: Path, work: Path) -> Path:
    """The zip notarytool needs for an app (ditto keeps the bundle intact)."""
    work.mkdir(parents=True, exist_ok=True)
    target = work / f"{app.stem}.zip"
    if target.exists():
        target.unlink()
    ctx.must(["ditto", "-c", "-k", "--keepParent", str(app), str(target)], f"ditto {app.name}")
    return target
