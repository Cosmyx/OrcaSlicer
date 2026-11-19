"""Cosmyx macOS signing: Developer ID signing, notarisation and stapling of the
universal macOS build (wiki/cosmyx/macos-signing.md, decisions 0150-0158).

The composite action .github/actions/cosmyx-sign-macos prepares a keychain and
runs cli.py, which signs every .app of build/universal/OrcaSlicer inside out,
notarises and staples it, rebuilds the DMGs under their usual names, signs,
notarises and staples them, then verifies the result.

Every external tool (codesign, xcrun, ditto, hdiutil, spctl) is called through
an injectable runner, so the whole flow is tested with a fake one. Standard
library only.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
COSMYX_DIR = PACKAGE_DIR.parent
REPO_ROOT = COSMYX_DIR.parents[1]
ENTITLEMENTS = REPO_ROOT / "scripts" / "disable_validation.entitlements"
ADHOC = "-"
REDACTED = "***"

Runner = Callable[..., subprocess.CompletedProcess]
Sleeper = Callable[[float], None]


class SigningError(RuntimeError):
    """A signing, notarisation or verification step failed; the message is safe to print."""


@dataclass
class Settings:
    """What the run needs, read from the environment by cli.py.

    identity is the codesign identity (the certificate's SHA-1 or its full
    name), or "-" for an ad-hoc dry run, which skips notarisation."""

    identity: str
    team_id: str = ""
    apple_id: str = ""
    app_password: str = ""
    keychain: str = ""
    entitlements: Path = ENTITLEMENTS

    @property
    def adhoc(self) -> bool:
        return self.identity == ADHOC

    def secrets(self) -> list[str]:
        """Values never printed: everything a log line could leak."""
        values = [self.apple_id, self.app_password, self.team_id]
        if not self.adhoc:
            values.append(self.identity)
        return [value for value in values if value]


@dataclass
class Context:
    """The runner, the sleeper and the output of one run."""

    settings: Settings
    run: Runner = subprocess.run
    sleep: Sleeper = time.sleep
    which: Callable[[str], str | None] = shutil.which
    out: Callable[[str], None] = field(default=lambda line: print(line, flush=True))
    summary: list[str] = field(default_factory=list)

    def redact(self, text: str) -> str:
        for value in sorted(self.settings.secrets(), key=len, reverse=True):
            text = text.replace(value, REDACTED)
        return text

    def say(self, line: str) -> None:
        self.out(self.redact(line))

    def note(self, line: str) -> None:
        """A line for the step summary (and the log)."""
        line = self.redact(line)
        self.summary.append(line)
        self.out(line)

    def call(self, args: Sequence[str | Path]) -> subprocess.CompletedProcess:
        return self.run([str(a) for a in args], capture_output=True, text=True, check=False)

    def must(self, args: Sequence[str | Path], what: str) -> subprocess.CompletedProcess:
        done = self.call(args)
        if done.returncode != 0:
            raise SigningError(self.redact(f"{what} failed (exit {done.returncode}): {tail(done)}"))
        return done


def tail(done: subprocess.CompletedProcess, lines: int = 5) -> str:
    text = ((done.stderr or "") + "\n" + (done.stdout or "")).strip().splitlines()
    return " | ".join(text[-lines:]) if text else "no output"


def chunks(items: Sequence, size: int) -> Iterable[Sequence]:
    for start in range(0, len(items), size):
        yield items[start:start + size]


def import_artifact_checks() -> None:
    """Make scripts/cosmyx importable (cli.py runs with python -I)."""
    if str(COSMYX_DIR) not in sys.path:
        sys.path.insert(0, str(COSMYX_DIR))
