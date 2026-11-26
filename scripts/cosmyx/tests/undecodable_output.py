"""Shared helper for the artifact checks tests: a child process whose output
is not valid text in any locale."""

from __future__ import annotations

import subprocess
import sys

# Bytes that are invalid in UTF-8 and undefined in cp1252, so a strict decode
# fails whatever the locale of the runner.
UNDECODABLE = b"\x81\x8d\xff"


def run_printing(args, kwargs: dict, out: bytes, code: int = 0) -> subprocess.CompletedProcess:
    """Run a real child that prints `out` and exits with `code`, decoded with
    the caller's own subprocess options (text, errors, timeout)."""
    script = f"import sys; sys.stdout.buffer.write({out!r}); sys.exit({code})"
    done = subprocess.run([sys.executable, "-c", script], **{k: v for k, v in kwargs.items() if k != "cwd"})
    return subprocess.CompletedProcess(args, done.returncode, done.stdout, done.stderr)
