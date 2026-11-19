"""macOS artifacts: mount each DMG read-only and check its Mach-O files (decision 0146).

Enforced in every mode:
- arch: `lipo -archs` gives exactly the family's architectures (universal: arm64
  and x86_64), unless an arch-exempt allowlist entry covers the file;
- macho_sig: `codesign --verify --strict --arch arm64` passes for every file
  with an arm64 slice (an ad-hoc signature is enough, unsigned arm64 code does
  not run on Apple silicon).
Reported only: bundle_sig, `codesign --verify --deep --strict` of each .app and
its signature class (Developer ID signing is deferred).
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable
from pathlib import Path

from . import binfmt
from .allowlist import Allowlist
from .inventory import Artifact
from .records import Record, build_manifest, posix_relative

Runner = Callable[..., subprocess.CompletedProcess]
TreeHook = Callable[[Artifact, Path], list[Record]]


def _run(run: Runner, args: list[str]) -> subprocess.CompletedProcess:
    return run(args, capture_output=True, text=True, errors="replace", check=False)


def _last_line(done: subprocess.CompletedProcess) -> str:
    lines = (done.stderr or done.stdout or "").strip().splitlines()
    return lines[-1] if lines else f"exit {done.returncode}"


def arch_record(artifact: Artifact, rel: str, file: Path, expected: list[str], allow: Allowlist,
                run: Runner) -> Record:
    done = _run(run, ["lipo", "-archs", str(file)])
    if done.returncode != 0:
        return Record("macos", artifact.name, rel, "arch", "fail", f"lipo -archs failed: {_last_line(done)}")
    found = sorted(done.stdout.split())
    if found == sorted(expected):
        return Record("macos", artifact.name, rel, "arch", "pass", " ".join(found))
    entry = allow.find("macos", "arch-exempt", rel)
    if entry:
        return Record("macos", artifact.name, rel, "arch", "pass", f"arch-exempt ({' '.join(found)}): {entry.reason}",
                      {"entry": entry.index, "archs": found})
    return Record("macos", artifact.name, rel, "arch", "fail",
                  f"architectures {' '.join(found) or 'none'}, expected {' '.join(sorted(expected))}", {"archs": found})


def macho_sig_record(artifact: Artifact, rel: str, file: Path, fmt: binfmt.BinaryFormat, run: Runner) -> Record:
    if "arm64" not in fmt.archs:
        return Record("macos", artifact.name, rel, "macho_sig", "skip", "no arm64 slice", {"by_design": True})
    if fmt.is_object:
        return Record("macos", artifact.name, rel, "macho_sig", "skip", "object file, not loadable code",
                      {"by_design": True})
    done = _run(run, ["codesign", "--verify", "--strict", "--arch", "arm64", str(file)])
    if done.returncode == 0:
        return Record("macos", artifact.name, rel, "macho_sig", "pass", "arm64 slice signed")
    return Record("macos", artifact.name, rel, "macho_sig", "fail", f"arm64 slice: {_last_line(done)}")


def signature_class(codesign_dv: str) -> str:
    if re.search(r"^Authority=Developer ID Application:", codesign_dv, re.MULTILINE):
        return "developer-id"
    if re.search(r"^Signature=adhoc", codesign_dv, re.MULTILINE):
        return "adhoc"
    if "not signed at all" in codesign_dv:
        return "unsigned"
    return "other"


def bundle_records(artifact: Artifact, mount: Path, run: Runner) -> list[Record]:
    records = []
    for app in sorted(p for p in mount.iterdir() if p.suffix == ".app" and p.is_dir() and not p.is_symlink()):
        rel = app.name
        verify = _run(run, ["codesign", "--verify", "--deep", "--strict", str(app)])
        info = _run(run, ["codesign", "-dv", str(app)])
        klass = signature_class((info.stderr or "") + (info.stdout or ""))
        details = {"class": klass, "deep_verify": verify.returncode == 0}
        if klass == "developer-id" and verify.returncode == 0:
            records.append(Record("macos", artifact.name, rel, "bundle_sig", "pass", "Developer ID signed", details))
        else:
            why = "" if verify.returncode == 0 else f"; deep verify: {_last_line(verify)}"
            records.append(Record("macos", artifact.name, rel, "bundle_sig", "warn",
                                  f"not Developer-ID signed (expected, 0146): {klass}{why}", details))
    return records


def scan_tree(artifact: Artifact, mount: Path, allow: Allowlist, run: Runner) -> list[Record]:
    expected = artifact.spec.get("mac_archs", [])
    records = []
    machos = binfmt.walk(mount, "macho")
    if not machos:
        records.append(Record("macos", artifact.name, "", "arch", "fail", "no Mach-O file in the disk image"))
    for file, fmt in machos:
        rel = posix_relative(file, mount)
        records.append(arch_record(artifact, rel, file, expected, allow, run))
        records.append(macho_sig_record(artifact, rel, file, fmt, run))
    records += bundle_records(artifact, mount, run)
    return records


def check(artifacts_dir: Path, artifacts: list[Artifact], work: Path, allow: Allowlist, run: Runner = subprocess.run,
          tree_hook: TreeHook | None = None, manifests: dict | None = None,
          enforce_stale: bool = False) -> list[Record]:
    records = []
    for index, artifact in enumerate(artifacts):
        dmgs = sorted((artifacts_dir / artifact.name).glob("*.dmg"))
        if not dmgs:
            records.append(Record("macos", artifact.name, "", "arch", "fail", "no .dmg in the artifact"))
            continue
        mount = work / f"mnt{index}"
        mount.mkdir(parents=True, exist_ok=True)
        attach = _run(run, ["hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen", "-mountpoint", str(mount),
                            str(dmgs[0])])
        if attach.returncode != 0:
            records.append(Record("macos", artifact.name, dmgs[0].name, "arch", "fail",
                                  f"hdiutil attach failed: {_last_line(attach)}"))
            continue
        try:
            records += scan_tree(artifact, mount, allow, run)
            if manifests is not None:
                manifests[artifact.name] = build_manifest(mount)
            if tree_hook and artifact.spec.get("app"):
                records += tree_hook(artifact, mount)
        finally:
            if _run(run, ["hdiutil", "detach", str(mount)]).returncode != 0:
                _run(run, ["hdiutil", "detach", "-force", str(mount)])
    records += allow.stale_records("macos", enforce=enforce_stale)
    return records
