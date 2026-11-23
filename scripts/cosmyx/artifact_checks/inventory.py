"""What a build run produced: artifact families, the required set and the names.

Artifact names come from build_orca.yml; the patterns live in
data/expectations.json so that a renamed artifact is one data change.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import DATA_DIR
from .records import Record

HASH = re.compile(r"[0-9a-f]{7,40}")


def load_expectations(path: Path | None = None) -> dict:
    return json.loads((path or DATA_DIR / "expectations.json").read_text(encoding="utf-8"))


@dataclass
class Artifact:
    name: str
    family: str
    os: str
    kind: str
    arch: str = ""
    msvc: bool = False
    id: int | None = None
    expired: bool = False
    tag: str = ""
    spec: dict = field(default_factory=dict)

    def to_json(self) -> dict:
        return {"name": self.name, "family": self.family, "os": self.os, "kind": self.kind,
                "arch": self.arch, "msvc": self.msvc, "id": self.id, "tag": self.tag}


def classify(name: str, expectations: dict, artifact_id: int | None = None, expired: bool = False) -> Artifact | None:
    """The family of an artifact name (first matching pattern), or None."""
    for spec in expectations["families"]:
        match = re.search(spec["regex"], name)
        if not match:
            continue
        groups = match.groupdict()
        arch = (groups.get("arch") or "").lstrip("_") or spec.get("default_arch", "")
        return Artifact(name, spec["id"], spec["os"], spec["kind"], arch, bool(groups.get("msvc")),
                        artifact_id, expired, groups.get("tag") or "", spec)
    return None


def inventory(artifacts: list[dict], expectations: dict) -> dict[str, list[Artifact]]:
    """Group the run's artifacts (GitHub API objects) by OS. Ignored families
    and unknown names are left out."""
    by_os: dict[str, list[Artifact]] = {"windows": [], "macos": [], "linux": []}
    for item in artifacts:
        found = classify(item["name"], expectations, item.get("id"), bool(item.get("expired")))
        if found and found.kind != "ignored":
            by_os[found.os].append(found)
    for items in by_os.values():
        items.sort(key=lambda artifact: artifact.name)
    return by_os


def required_applies(run: dict, expectations: dict) -> tuple[bool, str]:
    """Whether the required set is enforced for this build run, and why not."""
    rules = expectations["required"]
    branch = run.get("head_branch") or ""
    if not any(re.search(pattern, branch) for pattern in rules["branches"]):
        return False, f"branch {branch!r} is not DEV or release/*"
    if run.get("event") not in rules["events"]:
        return False, f"event {run.get('event')!r} has no required set"
    if run.get("conclusion") != "success":
        return False, f"build concluded {run.get('conclusion')!r}, not success"
    return True, ""


def required_records(run: dict, found: dict[str, list[Artifact]], expectations: dict) -> list[Record]:
    applies, why = required_applies(run, expectations)
    records = []
    for rule in expectations["required"]["artifacts"]:
        family_os = next(spec["os"] for spec in expectations["families"] if spec["id"] == rule["family"])
        label = f"{rule['family']}{' ' + rule['arch'] if rule['arch'] else ''}"
        if not applies or run.get("event") not in rule.get("events", expectations["required"]["events"]):
            reason = why or f"not built on {run.get('event')} runs"
            records.append(Record(family_os, label, "", "required", "skip", reason, {"by_design": True}))
            continue
        present = [a for a in found.get(family_os, [])
                   if a.family == rule["family"] and a.arch == rule["arch"] and not a.msvc and not a.expired]
        if present:
            records.append(Record(family_os, present[0].name, "", "required", "pass"))
        else:
            records.append(Record(family_os, label, "", "required", "fail",
                                  f"required artifact {label} is missing from a successful {run.get('head_branch')} build"))
    return records


def build_tag_hash(name: str, display_version: str, head_sha: str) -> tuple[bool, str]:
    """Whether a name carries <display version>_<hash>, the hash a prefix of head_sha."""
    for match in re.finditer(re.escape(display_version) + r"_([0-9a-f]+)", name):
        commit = match.group(1)
        if HASH.fullmatch(commit) and head_sha.startswith(commit):
            return True, commit
    return False, ""


def names_records(names: list[str], display_version: str | None, head_sha: str, expectations: dict,
                  os_name: str = "any") -> list[Record]:
    """Every artifact with a product prefix (OrcaSlicer_ or CosmoSlice_, both
    accepted while the rename lands) is named after the build tag (T6, decision 0062)."""
    excludes = [re.compile(p) for p in expectations.get("name_check_excludes", [])]
    prefixes = tuple(expectations.get("name_prefixes", ["OrcaSlicer_"]))
    targets = [n for n in sorted(names) if n.startswith(prefixes) and not any(p.search(n) for p in excludes)]
    if display_version is None:
        return [Record(os_name, name, "", "names", "skip", "T6 not merged: the build has no Cosmyx version")
                for name in targets]
    records = []
    for name in targets:
        ok, commit = build_tag_hash(name, display_version, head_sha)
        if ok:
            records.append(Record(os_name, name, "", "names", "pass", details={"hash": commit}))
        else:
            records.append(Record(os_name, name, "", "names", "fail",
                                  f"name does not carry {display_version}_<hash of {head_sha[:12]}>"))
    return records
