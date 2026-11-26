"""The reviewed list of binaries that are not ours (decision 0145).

data/allowlist.json, read from the trusted checkout only:

    {"version": 1, "entries": [{
        "os": "windows" | "macos",
        "kind": "vendor" | "unsigned-ok" | "arch-exempt",
        "glob": "<path inside the artifact, POSIX, case-insensitive; * crosses />",
        "publisher_subject": "<signer subject>",   # vendor only, required
        "require_timestamp": true,                 # vendor only, optional
        "reason": "<why>",                         # required
        "expires": "YYYY-MM-DD"                    # optional
    }]}

An unknown key, a missing reason or an expired entry makes the list invalid.
"unsigned-ok" never covers a file the build signs by name (installer,
uninstaller, the app and the validator).
"""

from __future__ import annotations

import datetime as dt
import fnmatch
import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from . import DATA_DIR
from .records import Record

KINDS = ("vendor", "unsigned-ok", "arch-exempt")
ENTRY_KEYS = {"os", "kind", "glob", "publisher_subject", "require_timestamp", "reason", "expires"}


class AllowlistError(Exception):
    pass


@dataclass
class Entry:
    index: int
    os: str
    kind: str
    glob: str
    reason: str
    publisher_subject: str = ""
    require_timestamp: bool = True
    expires: dt.date | None = None

    def matches(self, path: str) -> bool:
        return fnmatch.fnmatchcase(path.lower(), self.glob.lower())


@dataclass
class Allowlist:
    entries: list[Entry] = field(default_factory=list)
    used: set[int] = field(default_factory=set)

    def find(self, os_name: str, kind: str, path: str) -> Entry | None:
        for entry in self.entries:
            if entry.os == os_name and entry.kind == kind and entry.matches(path):
                self.used.add(entry.index)
                return entry
        return None

    def stale_records(self, os_name: str, enforce: bool) -> list[Record]:
        """Entries of this OS that matched nothing once every artifact was scanned."""
        records = []
        for entry in self.entries:
            if entry.os == os_name and entry.index not in self.used:
                records.append(Record(os_name, "allowlist", entry.glob, "signature" if os_name == "windows" else "arch",
                                      "fail" if enforce else "warn",
                                      f"stale allowlist entry #{entry.index} ({entry.kind}): matched no file",
                                      {"entry": entry.index}))
        return records


def parse(data: dict, today: dt.date) -> Allowlist:
    if not isinstance(data, dict) or data.get("version") != 1 or set(data) - {"version", "entries"}:
        raise AllowlistError("allowlist: expected {\"version\": 1, \"entries\": [...]}")
    entries = []
    for index, raw in enumerate(data.get("entries", [])):
        where = f"allowlist entry #{index}"
        if not isinstance(raw, dict):
            raise AllowlistError(f"{where}: not an object")
        unknown = set(raw) - ENTRY_KEYS
        if unknown:
            raise AllowlistError(f"{where}: unknown keys {sorted(unknown)}")
        if raw.get("os") not in ("windows", "macos"):
            raise AllowlistError(f"{where}: os must be windows or macos")
        if raw.get("kind") not in KINDS:
            raise AllowlistError(f"{where}: kind must be one of {', '.join(KINDS)}")
        if not str(raw.get("glob", "")).strip():
            raise AllowlistError(f"{where}: glob is required")
        if not str(raw.get("reason", "")).strip():
            raise AllowlistError(f"{where}: reason is required")
        if raw["kind"] == "vendor" and not str(raw.get("publisher_subject", "")).strip():
            raise AllowlistError(f"{where}: a vendor entry needs publisher_subject")
        if raw["kind"] != "vendor" and ("publisher_subject" in raw or "require_timestamp" in raw):
            raise AllowlistError(f"{where}: publisher_subject and require_timestamp are for vendor entries")
        expires = None
        if "expires" in raw:
            try:
                expires = dt.date.fromisoformat(raw["expires"])
            except (TypeError, ValueError):
                raise AllowlistError(f"{where}: expires must be YYYY-MM-DD") from None
            if expires < today:
                raise AllowlistError(f"{where}: expired on {expires.isoformat()}")
        entries.append(Entry(index, raw["os"], raw["kind"], raw["glob"], raw["reason"],
                             raw.get("publisher_subject", ""), bool(raw.get("require_timestamp", True)), expires))
    return Allowlist(entries)


def load(path: Path | None = None, today: dt.date | None = None) -> Allowlist:
    path = path or DATA_DIR / "allowlist.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AllowlistError(f"allowlist: cannot read {path.name}: {error}") from None
    return parse(data, today or dt.date.today())


def is_own_name(path: str, own_names: list[str]) -> bool:
    name = PurePosixPath(path).name.lower()
    return any(fnmatch.fnmatchcase(name, pattern.lower()) for pattern in own_names)
