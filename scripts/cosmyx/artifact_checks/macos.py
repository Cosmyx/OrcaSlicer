"""macOS artifacts: mount each DMG read-only and check its Mach-O files
(decisions 0146, 0156).

Enforced in every mode:
- arch: `lipo -archs` gives exactly the family's architectures (universal: arm64
  and x86_64), unless an arch-exempt allowlist entry covers the file;
- macho_sig: `codesign --verify --strict --arch arm64` passes for every file
  with an arm64 slice (an ad-hoc signature is enough, unsigned arm64 code does
  not run on Apple silicon).

bundle_sig, `codesign --verify --deep --strict` of each .app and its signature
class, is reported only, unless the build was Developer ID signed (enforce
mode, decision 0156: the 0098 predicate and the seven Apple secrets set). In
enforce mode it must be Developer ID of the COSMYX_MAC_TEAM_ID team, and these
are checked too:
- macho_identity: every Mach-O file has a Developer ID authority, the team,
  the hardened runtime, a secure timestamp and no get-task-allow;
- dmg_sig: the DMG is Developer ID signed by the team;
- notarization: the DMG and its apps are stapled, Gatekeeper sees a notarised
  Developer ID app (`spctl -t exec`) and accepts the DMG (`spctl -t open`).
In not-configured mode with strict, the missing signing is a failure.

Then, while the image is mounted and the build may be run, the smoke run and
the slice of smoke_native.py (decision 0160).
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from . import binfmt, signing_policy, smoke_native
from .allowlist import Allowlist
from .inventory import Artifact
from .records import Record, build_manifest, posix_relative

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from macos_signing.verify import NOTARIZED, file_problems, parse_display  # noqa: E402

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


def _display(run: Runner, path: Path, entitlements: bool = False) -> tuple[str, str]:
    """(codesign -d text, entitlements XML) of one file or bundle. codesign
    prints the signature details on stderr and the entitlements on stdout."""
    args = ["codesign", "-d", "--verbose=4"] + (["--entitlements", "-", "--xml"] if entitlements else []) + [str(path)]
    done = _run(run, args)
    if not entitlements:
        return (done.stderr or "") + (done.stdout or ""), ""
    return done.stderr or "", (done.stdout or "") if done.returncode == 0 else ""


def bundle_records(artifact: Artifact, mount: Path, run: Runner, mode: str = signing_policy.REPORT,
                   team: str = "") -> list[Record]:
    records = []
    enforce = mode == signing_policy.ENFORCE
    for app in sorted(p for p in mount.iterdir() if p.suffix == ".app" and p.is_dir() and not p.is_symlink()):
        rel = app.name
        verify = _run(run, ["codesign", "--verify", "--deep", "--strict", str(app)])
        text, _ = _display(run, app)
        klass = signature_class(text)
        found_team = parse_display(text).team
        details = {"class": klass, "deep_verify": verify.returncode == 0}
        if klass == "developer-id" and verify.returncode == 0 and (not enforce or found_team == team):
            records.append(Record("macos", artifact.name, rel, "bundle_sig", "pass", "Developer ID signed", details))
        elif enforce:
            why = [f"signature class {klass}"] if klass != "developer-id" else []
            if verify.returncode != 0:
                why.append(f"deep verify: {_last_line(verify)}")
            if klass == "developer-id" and found_team != team:
                why.append(f"team {found_team or 'not set'}, expected the TEAM_ID team")
            records.append(Record("macos", artifact.name, rel, "bundle_sig", "fail", "; ".join(why), details))
        else:
            why = "" if verify.returncode == 0 else f"; deep verify: {_last_line(verify)}"
            records.append(Record("macos", artifact.name, rel, "bundle_sig", "warn",
                                  f"not Developer-ID signed (expected, 0146): {klass}{why}", details))
    return records


def macho_identity_record(artifact: Artifact, rel: str, file: Path, team: str, run: Runner) -> Record:
    text, entitlements = _display(run, file, entitlements=True)
    problems = file_problems(parse_display(text), entitlements, team, adhoc=False)
    if problems:
        return Record("macos", artifact.name, rel, "macho_identity", "fail", "; ".join(problems))
    return Record("macos", artifact.name, rel, "macho_identity", "pass", "Developer ID, team, runtime, timestamp")


def _gatekeeper(run: Runner, args: list[str]) -> str:
    """Empty when spctl accepts a notarised Developer ID, else why not."""
    done = _run(run, args)
    text = (done.stderr or "") + (done.stdout or "")
    if done.returncode == 0 and "accepted" in text and NOTARIZED in text:
        return ""
    return _last_line(done)


def dmg_records(artifact: Artifact, dmg: Path, mount: Path, team: str, run: Runner) -> list[Record]:
    """Enforce mode only: the DMG's own signature, and the notarisation of the
    DMG and of each app inside it."""
    records = []
    verify = _run(run, ["codesign", "--verify", "--strict", str(dmg)])
    text, _ = _display(run, dmg)
    sig = parse_display(text)
    why = []
    if verify.returncode != 0:
        why.append(f"verify: {_last_line(verify)}")
    if signature_class(text) != "developer-id":
        why.append(f"signature class {signature_class(text)}")
    if sig.team != team:
        why.append(f"team {sig.team or 'not set'}, expected the TEAM_ID team")
    records.append(Record("macos", artifact.name, dmg.name, "dmg_sig", "fail" if why else "pass",
                          "; ".join(why) or "Developer ID signed"))
    targets = [(dmg.name, dmg, ["spctl", "-a", "-vvv", "-t", "open", "--context", "context:primary-signature",
                                str(dmg)])]
    for app in sorted(p for p in mount.iterdir() if p.suffix == ".app" and p.is_dir() and not p.is_symlink()):
        targets.append((app.name, app, ["spctl", "-a", "-vvv", "-t", "exec", str(app)]))
    for rel, path, spctl in targets:
        why = []
        stapled = _run(run, ["xcrun", "stapler", "validate", str(path)])
        if stapled.returncode != 0:
            why.append(f"not stapled: {_last_line(stapled)}")
        refused = _gatekeeper(run, spctl)
        if refused:
            why.append(f"Gatekeeper: {refused}")
        records.append(Record("macos", artifact.name, rel, "notarization", "fail" if why else "pass",
                              "; ".join(why) or "notarised and stapled"))
    return records


def scan_tree(artifact: Artifact, mount: Path, allow: Allowlist, run: Runner, mode: str = signing_policy.REPORT,
              team: str = "") -> list[Record]:
    expected = artifact.spec.get("mac_archs", [])
    enforce = mode == signing_policy.ENFORCE
    records = []
    machos = binfmt.walk(mount, "macho")
    if not machos:
        records.append(Record("macos", artifact.name, "", "arch", "fail", "no Mach-O file in the disk image"))
    for file, fmt in machos:
        rel = posix_relative(file, mount)
        records.append(arch_record(artifact, rel, file, expected, allow, run))
        records.append(macho_sig_record(artifact, rel, file, fmt, run))
        if enforce and not fmt.is_object:
            records.append(macho_identity_record(artifact, rel, file, team, run))
    records += bundle_records(artifact, mount, run, mode, team)
    return records


def check(artifacts_dir: Path, artifacts: list[Artifact], work: Path, allow: Allowlist, run: Runner = subprocess.run,
          tree_hook: TreeHook | None = None, manifests: dict | None = None,
          enforce_stale: bool = False, mode: str = signing_policy.REPORT, team: str = "",
          strict: bool = False, exec_ok: bool = False, subject: Path | None = None,
          expectations: dict | None = None, host_arch: str | None = None) -> list[Record]:
    """Mount each disk image and check it. The smoke run and the slice need
    expectations and subject (the built commit's data files)."""
    records = []
    enforce = mode == signing_policy.ENFORCE
    if enforce and not team:
        records.append(Record("macos", "signing", "", "macho_identity", "fail",
                              "COSMYX_MAC_TEAM_ID is empty: the check job needs the TEAM_ID secret (0156)"))
    if mode == signing_policy.NOT_CONFIGURED and strict:
        records.append(Record("macos", "signing", "", "bundle_sig", "fail",
                              "macOS signing is not configured: the Apple signing secrets are not all set (0151)"))
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
        # Only the universal app and the profile validator are Developer ID
        # signed (T15); the per-arch DMGs stay ad-hoc and are reported only.
        own_mode = mode if artifact.spec.get("developer_id") else signing_policy.REPORT
        try:
            records += scan_tree(artifact, mount, allow, run, own_mode, team)
            if own_mode == signing_policy.ENFORCE:
                records += dmg_records(artifact, dmgs[0], mount, team, run)
            if manifests is not None:
                manifests[artifact.name] = build_manifest(mount)
            if tree_hook and artifact.spec.get("app"):
                records += tree_hook(artifact, mount)
            if expectations is not None and subject is not None and artifact.spec.get("app"):
                records += smoke_native.macos_records(artifact, mount, subject, work, expectations, exec_ok, run,
                                                      host_arch)
        finally:
            if _run(run, ["hdiutil", "detach", str(mount)]).returncode != 0:
                _run(run, ["hdiutil", "detach", "-force", str(mount)])
    records += allow.stale_records("macos", enforce=enforce_stale)
    return records
