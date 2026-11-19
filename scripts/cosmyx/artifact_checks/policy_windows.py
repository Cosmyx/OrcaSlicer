"""Windows artifacts: unpack them, collect signature facts, apply the rules.

Collection (Windows runner only) unpacks every Windows artifact: the portable
folder, the NSIS installer (7-Zip >= 23.01) and the uninstaller a silent
install writes (x64 only), the profile validator and the MSIX package. Every
PE found by its magic bytes goes to facts_windows.ps1, which reports facts and
decides nothing (decision 0142). evaluate() turns the facts into records
(decision 0143).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from . import PACKAGE_DIR, binfmt
from .allowlist import Allowlist, is_own_name
from .inventory import Artifact
from .records import Record, posix_relative
from .signing_policy import ENFORCE, NOT_CONFIGURED, NOTICE

CODE_SIGNING_EKU = "1.3.6.1.5.5.7.3.3"
ARTIFACT_SIGNING_EKU = "1.3.6.1.4.1.311.97.1.0"
TRUSTED_SIGNING_EKU = re.compile(r"^1\.3\.6\.1\.4\.1\.311\.97(\.[0-9]+)+$")
SEVEN_ZIP_VERSION = re.compile(r"7-Zip(?: \(\w+\))? ([0-9]+)\.([0-9]+)")
FACTS_SCRIPT = PACKAGE_DIR / "facts_windows.ps1"

Runner = Callable[..., subprocess.CompletedProcess]


@dataclass
class Item:
    """One PE to check: where it was found and the path rules match against."""
    artifact: str
    path: str  # shown in records, POSIX, relative to the artifact
    match_path: str  # path inside the app (NSIS prefixes stripped)
    role: str  # portable, payload, installed, installer, validator, msix
    arch: str = ""
    msvc: bool = False
    file: Path | None = None


@dataclass
class Identity:
    subject: str = ""
    eku: str = ""


@dataclass
class Collected:
    items: list[Item] = field(default_factory=list)
    records: list[Record] = field(default_factory=list)
    trees: list[tuple[str, Path]] = field(default_factory=list)  # (artifact, app folder)


# ---------------------------------------------------------------------------
# Rules


def identity_records(identity: Identity, mode: str, facts: list[dict] | None = None) -> list[Record]:
    """Problems with the identity pins, and what the signatures carry when no
    pin is set (decision 0099)."""
    if mode != ENFORCE:
        return []
    if identity.eku and not TRUSTED_SIGNING_EKU.fullmatch(identity.eku):
        return [Record("windows", "settings", "COSMYX_SIGN_EKU", "signature", "fail",
                       f"COSMYX_SIGN_EKU {identity.eku!r} is not an Artifact Signing EKU (1.3.6.1.4.1.311.97.<n>...)")]
    if identity.eku:
        return []
    subjects, ekus = set(), set()
    for fact in facts or []:
        found = set(fact.get("signer_ekus") or [])
        if ARTIFACT_SIGNING_EKU in found and CODE_SIGNING_EKU in found:
            subjects.add(fact.get("signer_subject") or "")
            ekus |= {e for e in found if TRUSTED_SIGNING_EKU.fullmatch(e) and e != ARTIFACT_SIGNING_EKU}
    observed = {"subjects": sorted(subjects), "ekus": sorted(ekus)}
    if identity.subject:
        return [Record("windows", "settings", "COSMYX_SIGN_EKU", "signature", "warn",
                       "identity pinned by Subject only; set COSMYX_SIGN_EKU (stable across renewals) to pin it "
                       f"(observed: {', '.join(observed['ekus']) or 'none'})", observed)]
    return [Record("windows", "settings", "COSMYX_SIGN_EKU", "signature", "warn",
                   "no identity pin: any Artifact Signing certificate passes; set COSMYX_SIGN_EKU or "
                   f"COSMYX_SIGN_SUBJECT (observed subjects: {'; '.join(observed['subjects']) or 'none'}; "
                   f"EKUs: {', '.join(observed['ekus']) or 'none'})", observed)]


def is_ours(fact: dict, identity: Identity) -> bool:
    """Our certificate: Artifact Signing and code signing EKUs, plus the pins
    that are set (decision 0099)."""
    ekus = set(fact.get("signer_ekus") or [])
    if not (ARTIFACT_SIGNING_EKU in ekus and CODE_SIGNING_EKU in ekus):
        return False
    if identity.eku and (not TRUSTED_SIGNING_EKU.fullmatch(identity.eku) or identity.eku not in ekus):
        return False
    if identity.subject and (fact.get("signer_subject") or "") != identity.subject:
        return False
    return True


def _unsigned(fact: dict) -> bool:
    return not fact.get("signer_subject") or fact.get("auth_status") in ("NotSigned", None, "")


def _tail(fact: dict) -> str:
    tail = (fact.get("signtool_tail") or "").strip().splitlines()
    return tail[-1] if tail else ""


def enforce_record(item: Item, fact: dict, identity: Identity, allow: Allowlist, own_names: list[str]) -> Record:
    def rec(status: str, reason: str, **details) -> Record:
        return Record("windows", item.artifact, item.path, "signature", status, reason, details)

    if _unsigned(fact):
        entry = allow.find("windows", "unsigned-ok", item.match_path)
        if entry and not is_own_name(item.match_path, own_names):
            return rec("pass", f"unsigned, allowed: {entry.reason}", entry=entry.index)
        return rec("fail", "unsigned")
    if fact.get("signtool_exit") != 0:
        return rec("fail", f"signtool verify exit {fact.get('signtool_exit')}: {_tail(fact)}",
                   signer=fact.get("signer_subject"))
    if fact.get("auth_status") != "Valid":
        return rec("fail", f"signature status {fact.get('auth_status')}", signer=fact.get("signer_subject"))
    if is_ours(fact, identity):
        if not fact.get("timestamp_subject"):
            return rec("fail", "our signature has no timestamp")
        return rec("pass", "signed by us, timestamped")
    entry = allow.find("windows", "vendor", item.match_path)
    if entry is None:
        return rec("fail", f"signed by {fact.get('signer_subject')}: not ours and not in the allowlist",
                   signer=fact.get("signer_subject"))
    if fact.get("signer_subject") != entry.publisher_subject:
        return rec("fail", f"signed by {fact.get('signer_subject')}, allowlist entry #{entry.index} expects "
                           f"{entry.publisher_subject}", entry=entry.index)
    if entry.require_timestamp and not fact.get("timestamp_subject"):
        return rec("fail", f"vendor signature has no timestamp (allowlist entry #{entry.index})", entry=entry.index)
    return rec("pass", f"vendor: {entry.reason}", entry=entry.index)


def report_record(item: Item, fact: dict) -> Record:
    signed = not _unsigned(fact) and fact.get("signtool_exit") == 0 and fact.get("auth_status") == "Valid"
    reason = "signed" if signed else ("unsigned" if _unsigned(fact) else f"invalid signature ({fact.get('auth_status')})")
    return Record("windows", item.artifact, item.path, "signature", "pass", f"not enforced: {reason}",
                  {"signed": signed, "signer": fact.get("signer_subject")})


def payload_records(items: list[Item], facts: dict[str, dict]) -> list[Record]:
    """Every PE of the portable folder is in the installer payload with the same
    hash (decision 0143). Checked in every mode."""
    def hashes(role: str, arch: str, msvc: bool) -> dict[str, str]:
        found = {}
        for item in items:
            if item.role == role and item.arch == arch and item.msvc == msvc and item.file is not None:
                fact = facts.get(str(item.file))
                if fact:
                    found[item.match_path.lower()] = fact.get("sha256", "").lower()
        return found

    records = []
    pairs = sorted({(i.artifact, i.arch, i.msvc) for i in items if i.role == "portable"})
    for artifact, arch, msvc in pairs:
        portable = hashes("portable", arch, msvc)
        installers = sorted({i.artifact for i in items if i.role == "payload" and i.arch == arch and i.msvc == msvc})
        if not installers:
            records.append(Record("windows", artifact, "", "payload", "skip",
                                  "no installer payload of the same architecture to compare with"))
            continue
        payload = hashes("payload", arch, msvc)
        missing = sorted(p for p in portable if p not in payload)
        different = sorted(p for p in portable if p in payload and payload[p] != portable[p])
        details = {"installer": installers[0], "missing": missing[:50], "different": different[:50],
                   "compared": len(portable)}
        if missing or different:
            records.append(Record("windows", installers[0], "", "payload", "fail",
                                  f"{len(missing)} portable PE files missing from the payload, "
                                  f"{len(different)} with another hash", details))
        else:
            records.append(Record("windows", installers[0], "", "payload", "pass",
                                  f"the payload holds the {len(portable)} portable PE files unchanged", details))
    return records


def evaluate(items: list[Item], facts: dict[str, dict], mode: str, identity: Identity, allow: Allowlist,
             own_names: list[str], strict: bool) -> list[Record]:
    records = identity_records(identity, mode, list(facts.values()))
    unsigned = 0
    for item in items:
        if item.role == "msix-package":
            records.append(Record("windows", item.artifact, item.path, "signature", "pass",
                                  "MSIX package unsigned by design (Store signs it)", {"info": True}))
            continue
        fact = facts.get(str(item.file))
        if fact is None:
            records.append(Record("windows", item.artifact, item.path, "signature", "fail",
                                  "no signature facts collected for this file"))
            continue
        if mode == ENFORCE:
            records.append(enforce_record(item, fact, identity, allow, own_names))
        else:
            record = report_record(item, fact)
            unsigned += 0 if record.details["signed"] else 1
            records.append(record)
    if mode == ENFORCE:
        records += allow.stale_records("windows", enforce=True)
    else:
        status = "fail" if strict and mode == NOT_CONFIGURED else "warn"
        reason = NOTICE if mode == NOT_CONFIGURED else f"signatures reported, not enforced ({mode} mode)"
        records.append(Record("windows", "summary", "", "signature", status if (unsigned or mode == NOT_CONFIGURED) else "pass",
                              f"{reason}; {unsigned} unsigned or invalid PE files", {"unsigned": unsigned, "mode": mode}))
        records += allow.stale_records("windows", enforce=False)
    records += payload_records(items, facts)
    return records


# ---------------------------------------------------------------------------
# Collection


def strip_prefix(path: str, prefixes: list[str]) -> str:
    parts = PurePosixPath(path).parts
    if parts and parts[0] in prefixes:
        parts = parts[1:]
    return PurePosixPath(*parts).as_posix() if parts else path


def seven_zip_version(output: str) -> tuple[int, int] | None:
    match = SEVEN_ZIP_VERSION.search(output)
    return (int(match.group(1)), int(match.group(2))) if match else None


def seven_zip_ok(output: str, minimum: str) -> tuple[bool, str]:
    found = seven_zip_version(output)
    wanted = tuple(int(x) for x in minimum.split("."))
    if found is None:
        return False, "7-Zip version not recognised"
    return found >= wanted, f"7-Zip {found[0]}.{found[1]:02d}"


def find_seven_zip(env: dict) -> str | None:
    for candidate in (env.get("COSMYX_7Z", ""), str(Path(env.get("ProgramFiles", "C:/Program Files")) / "7-Zip" / "7z.exe")):
        if candidate and Path(candidate).is_file():
            return candidate
    return shutil.which("7z")


def _pe_items(root: Path, artifact: Artifact, role: str, prefix: str, prefixes: list[str]) -> list[Item]:
    items = []
    for path, _fmt in binfmt.walk(root, "pe"):
        rel = posix_relative(path, root)
        shown = f"{prefix}{rel}" if prefix else rel
        items.append(Item(artifact.name, shown, strip_prefix(rel, prefixes), role, artifact.arch, artifact.msvc, path))
    return items


def collect(artifacts_dir: Path, artifacts: list[Artifact], work: Path, expectations: dict, env: dict,
            run: Runner = subprocess.run, install: bool = True) -> Collected:
    settings = expectations["windows"]
    prefixes = settings["nsis_prefixes"]
    out = Collected()
    seven_zip = None
    for artifact in artifacts:
        root = artifacts_dir / artifact.name
        if not root.is_dir():
            out.records.append(Record("windows", artifact.name, "", "signature", "fail", "artifact was not downloaded"))
            continue
        if artifact.kind == "portable":
            out.items += _pe_items(root, artifact, "portable", "", prefixes)
            out.trees.append((artifact.name, root))
        elif artifact.kind == "validator":
            out.items += _pe_items(root, artifact, "validator", "", prefixes)
        elif artifact.kind == "msix":
            for package in sorted(root.glob("*.msix")):
                target = work / artifact.name / package.stem
                try:
                    with zipfile.ZipFile(package) as archive:
                        archive.extractall(target)
                except (zipfile.BadZipFile, OSError, EOFError) as error:
                    # A truncated or broken package is a finding for this
                    # artifact, not a reason to drop every other record.
                    out.records.append(Record("windows", artifact.name, package.name, "payload", "fail",
                                              f"the MSIX package is not a readable zip ({error})"))
                    continue
                out.items.append(Item(artifact.name, package.name, package.name, "msix-package", artifact.arch, artifact.msvc))
                out.items += _pe_items(target, artifact, "msix", f"{package.name}/", prefixes)
        elif artifact.kind == "installer":
            installers = sorted(root.glob("*.exe"))
            if not installers:
                out.records.append(Record("windows", artifact.name, "", "payload", "fail", "no installer .exe in the artifact"))
                continue
            installer = installers[0]
            out.items.append(Item(artifact.name, installer.name, installer.name, "installer", artifact.arch,
                                  artifact.msvc, installer))
            if seven_zip is None:
                seven_zip = find_seven_zip(env) or ""
                probe = run([seven_zip], capture_output=True, text=True, errors="replace", check=False) if seven_zip else None
                ok, why = seven_zip_ok(probe.stdout if probe else "", settings["seven_zip_min"])
                if not ok:
                    out.records.append(Record("windows", artifact.name, "", "payload", "fail",
                                              f"7-Zip >= {settings['seven_zip_min']} is needed to unpack NSIS installers ({why or 'not found'})"))
                    seven_zip = ""
            if seven_zip:
                payload = work / artifact.name / "payload"
                done = run([seven_zip, "x", "-y", f"-o{payload}", str(installer)], capture_output=True, text=True, errors="replace", check=False)
                if done.returncode != 0:
                    out.records.append(Record("windows", artifact.name, installer.name, "payload", "fail",
                                              f"7-Zip could not unpack the installer (exit {done.returncode})"))
                else:
                    out.items += _pe_items(payload, artifact, "payload", "payload/", prefixes)
            if artifact.arch != "x64":
                out.records.append(Record("windows", artifact.name, "installed/Uninstall.exe", "signature", "skip",
                                          f"{artifact.arch} installer is not run on the x64 runner", {"by_design": True}))
            elif not install:
                out.records.append(Record("windows", artifact.name, "installed/Uninstall.exe", "signature", "skip",
                                          "silent install disabled (local run)", {"by_design": True}))
            else:
                installed = work / artifact.name / "installed"
                # NSIS wants /D= last and unquoted, even with spaces.
                run([str(installer), "/S", f"/D={installed}"], check=False, timeout=900)
                uninstaller = installed / "Uninstall.exe"
                if uninstaller.is_file():
                    out.items.append(Item(artifact.name, "installed/Uninstall.exe", "Uninstall.exe", "installed",
                                          artifact.arch, artifact.msvc, uninstaller))
                else:
                    out.records.append(Record("windows", artifact.name, "installed/Uninstall.exe", "signature", "fail",
                                              "the silent install wrote no Uninstall.exe"))
    return out


def collect_facts(items: list[Item], work: Path, run: Runner = subprocess.run, powershell: str = "pwsh") -> dict[str, dict]:
    files = [str(item.file) for item in items if item.file is not None]
    if not files:
        return {}
    work.mkdir(parents=True, exist_ok=True)
    listing = work / "pe-files.txt"
    listing.write_text("".join(f + "\n" for f in files), encoding="utf-8")
    facts_out = work / "facts.jsonl"
    run([powershell, "-NoLogo", "-NoProfile", "-File", str(FACTS_SCRIPT), "-PathList", str(listing),
         "-Out", str(facts_out)], check=True)
    return read_facts(facts_out)


def read_facts(path: Path) -> dict[str, dict]:
    facts = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            fact = json.loads(line)
            facts[str(Path(fact["path"]))] = fact
    return facts
