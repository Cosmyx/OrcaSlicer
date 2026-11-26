"""Find a GitHub Actions job wherever the upstream base keeps it.

Cosmyx branches are replayed on several bases (DEV and OrcaSlicer release
tags), and upstream moves jobs between workflow files: the Flatpak build is a
job of `build_flatpak.yml` on DEV but a job inside `build_all.yml` on older
tags. Tests that pin a Cosmyx hook in such a job look it up here instead of
naming one file, and skip when no candidate file has the job.
"""

from __future__ import annotations

import re
from pathlib import Path

# Files that may hold the Flatpak build job, most specific first.
FLATPAK_CANDIDATES = (
    Path(".github") / "workflows" / "build_flatpak.yml",
    Path(".github") / "workflows" / "build_all.yml",
)


def read_workflow(path: Path) -> str:
    """Read a workflow as text with LF line endings (upstream ships some as CRLF)."""
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def jobs(text: str) -> dict[str, str]:
    """Split the jobs: section into {job id: job body} on two-space keys."""
    if "\njobs:\n" not in text:
        return {}
    section = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([A-Za-z0-9_-]+):[ \t]*\n", section, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


def own_keys(body: str) -> dict[str, str]:
    """The job-level keys (four-space indent) of a job body."""
    return dict(re.findall(r"^    ([a-z-]+):(.*)$", body, flags=re.MULTILINE))


def find_job(
    repo_root: Path, job: str, candidates: tuple[Path, ...] = FLATPAK_CANDIDATES
) -> tuple[Path, str, dict[str, str]] | None:
    """Return (workflow path, its LF text, its jobs) for the first candidate
    that defines `job` with its own steps, or None when none does.

    A job that only calls a reusable workflow (`uses:`) is not the job itself,
    so a caller such as `build_all.yml` on DEV is passed over.
    """
    for relative in candidates:
        path = repo_root / relative
        if not path.is_file():
            continue
        text = read_workflow(path)
        found = jobs(text)
        if job in found and "steps" in own_keys(found[job]):
            return path, text, found
    return None
