"""Smoke run and slice on Windows and macOS (decision 0160).

The same two runs as on Linux (decision 0147), from the shipped app:
- macOS: the app of the read-only mounted disk image, its executable taken
  from Info.plist (CFBundleExecutable); run when the runner's architecture is
  one of the family's;
- Windows: a temporary copy of the x64 portable folder, with the pinned Mesa
  in its mesa/ folder (mesa_win.py, decision 0161).

`<app> --help` within the smoke timeout, then a slice of the shipped cube
judged by slice.py on result.json and plate_*.gcode. Nothing runs for a fork
build (0141). A crash is named from its signal (macOS) or its NTSTATUS
exit code (Windows).
"""

from __future__ import annotations

import os
import platform
import plistlib
import shutil
import subprocess
import urllib.request
from collections.abc import Callable
from pathlib import Path
from xml.parsers.expat import ExpatError

from . import mesa_win, slice as slicer
from .content import find_resources
from .inventory import Artifact
from .linux import smoke_status
from .records import Record

Runner = Callable[..., subprocess.CompletedProcess]
NTSTATUS = {
    0x80000003: "STATUS_BREAKPOINT",
    0xC0000005: "STATUS_ACCESS_VIOLATION",
    0xC000001D: "STATUS_ILLEGAL_INSTRUCTION",
    0xC0000094: "STATUS_INTEGER_DIVIDE_BY_ZERO",
    0xC00000FD: "STATUS_STACK_OVERFLOW",
    0xC0000135: "STATUS_DLL_NOT_FOUND",
    0xC0000139: "STATUS_ENTRYPOINT_NOT_FOUND",
    0xC0000142: "STATUS_DLL_INIT_FAILED",
    0xC0000374: "STATUS_HEAP_CORRUPTION",
    0xC0000409: "STATUS_STACK_BUFFER_OVERRUN",
}
MAC_ARCHS = {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x86_64"}
# Darwin signal numbers (sys/signal.h): SIGBUS is 10 there, not Linux's 7. Fixed
# here because this module also runs on hosts whose signal module differs.
MACOS_CRASH_SIGNALS = {11: "SIGSEGV", 6: "SIGABRT", 10: "SIGBUS", 4: "SIGILL", 8: "SIGFPE"}


def windows_crash(returncode: int | None) -> str:
    """The NTSTATUS name of a Windows exit code that means a crash, else ''."""
    if returncode is None:
        return ""
    code = returncode & 0xFFFFFFFF
    if code in NTSTATUS:
        return f"{NTSTATUS[code]} (0x{code:08X})"
    if code >= 0xC0000000:
        return f"NTSTATUS 0x{code:08X}"
    return ""


def classify(os_name: str, returncode: int | None, output: str, timed_out: bool, timeout: int) -> tuple[str, str]:
    """Smoke status: a hang or a crash fails; a nonzero exit passes only after
    a usage text (the Linux rule, plus NTSTATUS crashes on Windows)."""
    if os_name == "windows" and not timed_out:
        crash = windows_crash(returncode)
        if crash:
            return "fail", f"crashed with {crash}"
    return smoke_status(returncode, output, timed_out, timeout, MACOS_CRASH_SIGNALS if os_name == "macos" else None)


def smoke(os_name: str, artifact: str, exe: Path, label: str, timeout: int, run: Runner,
          env: dict | None = None) -> Record:
    extra = {"env": env} if env is not None else {}
    try:
        # The app output is untrusted bytes: a strict decode would end the job.
        done = run([str(exe), "--help"], capture_output=True, text=True, errors="replace", check=False,
                   timeout=timeout, **extra)
        status, reason = classify(os_name, done.returncode, (done.stdout or "") + (done.stderr or ""), False, timeout)
    except subprocess.TimeoutExpired:
        status, reason = classify(os_name, None, "", True, timeout)
    except OSError as error:
        status, reason = "fail", f"could not start: {error}"
    return Record(os_name, artifact, label, "smoke", status, reason)


def name_crash(os_name: str, record: Record) -> Record:
    """Prefix a failed slice with the crash its exit code shows."""
    if record.status != "fail":
        return record
    code = record.details.get("exit")
    crash = windows_crash(code) if os_name == "windows" else ""
    if os_name != "windows" and isinstance(code, int) and code < 0:
        reason = classify(os_name, code, "", False, 0)[1]
        crash = reason.removeprefix("crashed with ") if reason.startswith("crashed with ") else ""
    if crash and not record.reason.startswith("crashed"):
        record.reason = f"crashed with {crash}; {record.reason}"
    return record


def skipped(os_name: str, artifact: str, reason: str, by_design: bool, status: str = "skip",
            details: dict | None = None) -> list[Record]:
    extra = dict(details or {})
    if by_design:
        extra["by_design"] = True
    return [Record(os_name, artifact, "", check, status, reason, dict(extra)) for check in ("smoke", "slice")]


def run_pair(os_name: str, artifact: str, exe: Path, label: str, resources: Path | None, subject: Path, work: Path,
             expectations: dict, run: Runner, env: dict | None, details: dict | None = None) -> list[Record]:
    settings = expectations[os_name]
    records = [smoke(os_name, artifact, exe, label, settings["smoke_timeout"], run, env)]
    if resources is None:
        records.append(Record(os_name, artifact, "", "slice", "fail", "no resources folder in the app"))
    else:
        records.append(name_crash(os_name, slicer.run_slice(artifact, exe, resources, subject, work, expectations, run,
                                                            xvfb=False, os_name=os_name, env=env)))
    for record in records:
        record.details.update(details or {})
    return records


# ---------------------------------------------------------------------------
# macOS


def host_mac_arch() -> str:
    return MAC_ARCHS.get(platform.machine().lower(), platform.machine().lower())


# What plistlib raises on a damaged file besides InvalidFileException (a
# ValueError): expat errors for broken XML, and lookup or type errors from
# malformed values such as a bad <date>.
PLIST_ERRORS = (OSError, ValueError, ExpatError, AttributeError, KeyError, TypeError, OverflowError, RecursionError)


def plain_file_name(name: object) -> bool:
    """A single path component: no separator, no dot entry, nothing empty."""
    return (isinstance(name, str) and name.strip() != "" and name not in (".", "..")
            and not any(c in name for c in "/\\\0"))


def inside(path: Path, folder: Path) -> bool:
    """True when path, symlinks resolved, sits directly in folder."""
    return path.resolve().parent == folder.resolve()


def app_executable(app: Path) -> Path:
    """Contents/MacOS/<CFBundleExecutable>, or the bundle's own name.

    The Info.plist comes from the artifact (a fork controls it): a name that is
    not a plain file name, or that resolves outside Contents/MacOS, is ignored
    like a missing one, so the smoke run never executes a file outside the app."""
    macos_dir = app / "Contents" / "MacOS"
    try:
        with open(app / "Contents" / "Info.plist", "rb") as handle:
            info = plistlib.load(handle)
    except PLIST_ERRORS:
        info = None
    name = info.get("CFBundleExecutable") if isinstance(info, dict) else None
    if plain_file_name(name) and inside(macos_dir / name, macos_dir):
        return macos_dir / name
    return macos_dir / app.stem


def macos_records(artifact: Artifact, mount: Path, subject: Path, work: Path, expectations: dict, exec_ok: bool,
                  run: Runner = subprocess.run, host_arch: str | None = None) -> list[Record]:
    if not exec_ok:
        return skipped("macos", artifact.name, "built from a fork: never executed (0141)", True)
    host_arch = host_arch or host_mac_arch()
    archs = artifact.spec.get("mac_archs", [])
    if host_arch not in archs:
        return skipped("macos", artifact.name, f"{' '.join(archs)} app is not run on the {host_arch} runner", True)
    apps = sorted(p for p in mount.iterdir() if p.suffix == ".app" and p.is_dir() and not p.is_symlink())
    if not apps:
        return skipped("macos", artifact.name, "no .app in the disk image", False, "fail")
    exe = app_executable(apps[0])
    if not inside(exe, apps[0] / "Contents" / "MacOS"):
        return skipped("macos", artifact.name, f"executable {exe.relative_to(mount).as_posix()} resolves outside "
                       "Contents/MacOS", False, "fail")
    if not exe.is_file():
        return skipped("macos", artifact.name, f"no executable {exe.relative_to(mount).as_posix()}", False, "fail")
    label = f"{exe.relative_to(mount).as_posix()} --help"
    return run_pair("macos", artifact.name, exe, label, find_resources(apps[0]), subject, work / artifact.name,
                    expectations, run, None)


# ---------------------------------------------------------------------------
# Windows


def windows_exe(portable: Path, names: list[str]) -> str | None:
    """The first of the expected exe names (an ordered preference list) that
    is a file of the portable folder: CosmoSlice.exe once the product is
    renamed, orca-slicer.exe for an unrenamed build."""
    return next((name for name in names if (portable / name).is_file()), None)


def windows_records(artifact: Artifact, portable: Path, subject: Path, work: Path, expectations: dict, exec_ok: bool,
                    env: dict | None = None, run: Runner = subprocess.run, opener=urllib.request.urlopen,
                    seven_zip: str | None = None, pause: float = 5.0) -> list[Record]:
    settings = expectations["windows"]
    if not exec_ok:
        return skipped("windows", artifact.name, "built from a fork: never executed (0141)", True)
    if artifact.arch not in settings["run_archs"]:
        return skipped("windows", artifact.name, f"{artifact.arch} app is not run on the x64 runner", True)
    exe_name = windows_exe(portable, settings["app_exe"])
    if exe_name is None:
        return skipped("windows", artifact.name, f"none of {', '.join(settings['app_exe'])} in the portable folder",
                       False, "fail")
    base = work / artifact.name / "run"
    copy = base / "app"
    if copy.exists():
        shutil.rmtree(copy)
    shutil.copytree(portable, copy, symlinks=True)
    env = dict(os.environ if env is None else env)
    try:
        prepared = mesa_win.prepare(copy, base, expectations, env, run, opener, seven_zip, pause)
    except mesa_win.MesaError as error:
        return skipped("windows", artifact.name, f"Mesa: {error.reason}", False, error.status)
    return run_pair("windows", artifact.name, copy / exe_name, f"{exe_name} --help", find_resources(copy), subject,
                    base, expectations, run, prepared.env, prepared.details)
