"""Check records and file hashing helpers shared by every OS job.

A record is one JSON object per line (JSONL):

    {"os", "artifact", "path", "check", "status", "reason", "details"}

`status` is pass, fail, warn or skip. A skip that is expected by design (a
binary that cannot run on the runner, for example) carries
details["by_design"] = true, so strict mode does not turn it into a failure.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable

OSES = ("windows", "macos", "linux", "any")
CHECKS = (
    "signature", "payload", "arch", "macho_sig", "bundle_sig", "macho_identity", "dmg_sig", "notarization",
    "elf", "smoke", "slice",
    "names", "translations", "models", "required",
)
STATUSES = ("pass", "fail", "warn", "skip")


@dataclass
class Record:
    os: str
    artifact: str
    path: str
    check: str
    status: str
    reason: str = ""
    details: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.os not in OSES:
            raise ValueError(f"unknown os {self.os!r}")
        if self.check not in CHECKS:
            raise ValueError(f"unknown check {self.check!r}")
        if self.status not in STATUSES:
            raise ValueError(f"unknown status {self.status!r}")

    @property
    def by_design(self) -> bool:
        return bool(self.details.get("by_design"))

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, ensure_ascii=False)


def write_jsonl(path: Path, records: Iterable[Record]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as out:
        for record in records:
            out.write(record.to_json() + "\n")


def read_jsonl(path: Path) -> list[Record]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(Record(**json.loads(line)))
    return records


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def posix_relative(path: Path, root: Path) -> str:
    return PurePosixPath(*path.relative_to(root).parts).as_posix()


def iter_files(root: Path) -> list[Path]:
    """Every regular file under root, in a stable order. Symbolic links are never
    followed (a DMG links /Applications)."""
    files = []
    for folder, _dirs, names in os.walk(root, followlinks=False):
        for name in names:
            path = Path(folder) / name
            if not path.is_symlink() and path.is_file():
                files.append(path)
    return sorted(files, key=lambda p: posix_relative(p, root))


def build_manifest(root: Path) -> list[dict]:
    """path (POSIX, relative), size and sha256 of every file, sorted by path."""
    return [
        {"path": posix_relative(p, root), "size": p.stat().st_size, "sha256": sha256_file(p)}
        for p in iter_files(root)
    ]


def sha256sums(files: Iterable[tuple[str, Path]]) -> str:
    """SHA256SUMS text (`<hash>  <name>`), sorted by name."""
    lines = [f"{sha256_file(path)}  {name}" for name, path in sorted(files, key=lambda item: item[0])]
    return "".join(line + "\n" for line in lines)
