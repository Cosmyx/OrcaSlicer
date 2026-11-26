"""Linux artifacts: unpack the AppImage, check its ELF files, run it (decision 0147).

- x86_64 AppImage: unpacked (`--appimage-extract` when the build may be run,
  else `unsquashfs` at the runtime's end, so a fork build is never executed),
  every ELF must be x86_64, then a smoke run (`AppRun --help` under xvfb) and
  a slice of the shipped cube (slice.py) when the build may be run.
- aarch64 AppImage: the runtime's ELF machine only; it cannot run on the x64
  runner.
- profile validator: its ELF machine.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path

from . import binfmt, slice as slicer
from .content import find_resources
from .inventory import Artifact
from .records import Record, build_manifest, posix_relative

Runner = Callable[..., subprocess.CompletedProcess]
TreeHook = Callable[[Artifact, Path], list[Record]]
# Linux signal numbers, fixed by the kernel ABI on x86_64 and aarch64. The exit
# codes come from a Linux process, while this module is also imported on
# Windows (no SIGBUS) and macOS (SIGBUS is 10), so the host's signal module
# must not be used.
CRASH_SIGNALS = {11: "SIGSEGV", 6: "SIGABRT", 7: "SIGBUS", 4: "SIGILL", 8: "SIGFPE"}
USAGE_WORDS = ("usage", "--help", "options")


def smoke_status(returncode: int | None, output: str, timed_out: bool, timeout: int,
                 crash_signals: dict[int, str] | None = None) -> tuple[str, str]:
    """A smoke run passes unless it hangs or crashes; a nonzero exit passes only
    when the app printed its usage. crash_signals maps the signal numbers of the
    OS the app ran on to their names (Linux by default)."""
    signals = CRASH_SIGNALS if crash_signals is None else crash_signals
    if timed_out:
        return "fail", f"did not exit within {timeout} s"
    if returncode is None:
        return "fail", "did not run"
    if returncode < 0 and -returncode in signals:
        return "fail", f"crashed with signal {signals[-returncode]}"
    if returncode > 128 and returncode - 128 in signals:
        return "fail", f"crashed with signal {signals[returncode - 128]}"
    if returncode == 0:
        return "pass", "exit 0"
    if any(word in output.lower() for word in USAGE_WORDS):
        return "pass", f"exit {returncode} after printing its usage"
    return "fail", f"exit {returncode} without a usage text"


def smoke(artifact: str, app_run: Path, timeout: int, run: Runner, xvfb: bool = True) -> Record:
    args = (["xvfb-run", "-a"] if xvfb else []) + [str(app_run), "--help"]
    try:
        # The app output is untrusted bytes: a strict decode would end the job.
        done = run(args, capture_output=True, text=True, errors="replace", check=False, timeout=timeout)
        status, reason = smoke_status(done.returncode, (done.stdout or "") + (done.stderr or ""), False, timeout)
    except subprocess.TimeoutExpired:
        status, reason = smoke_status(None, "", True, timeout)
    except OSError as error:
        status, reason = "fail", f"could not start: {error}"
    return Record("linux", artifact, "AppRun --help", "smoke", status, reason)


def elf_records(artifact: str, root: Path, expected: str) -> list[Record]:
    records = []
    elves = binfmt.walk(root, "elf")
    if not elves:
        return [Record("linux", artifact, "", "elf", "fail", "no ELF file found")]
    for path, fmt in elves:
        rel = posix_relative(path, root)
        if fmt.archs == [expected]:
            records.append(Record("linux", artifact, rel, "elf", "pass", expected))
        else:
            records.append(Record("linux", artifact, rel, "elf", "fail",
                                  f"ELF machine {' '.join(fmt.archs)}, expected {expected}"))
    return records


def extract(appimage: Path, target: Path, exec_ok: bool, run: Runner) -> tuple[Path | None, str]:
    target.mkdir(parents=True, exist_ok=True)
    root = target / "squashfs-root"
    if exec_ok:
        appimage.chmod(appimage.stat().st_mode | stat.S_IXUSR)
        done = run([str(appimage), "--appimage-extract"], cwd=target, capture_output=True, text=True, errors="replace", check=False)
        return (root, "") if done.returncode == 0 and root.is_dir() else (None, f"--appimage-extract exit {done.returncode}")
    offset = binfmt.elf_end(appimage)
    if offset is None or shutil.which("unsquashfs") is None:
        return None, "unsquashfs or the AppImage runtime offset is not available"
    done = run(["unsquashfs", "-no-progress", "-o", str(offset), "-d", str(root), str(appimage)],
               capture_output=True, text=True, errors="replace", check=False)
    return (root, "") if done.returncode == 0 and root.is_dir() else (None, f"unsquashfs exit {done.returncode}")


def check(artifacts_dir: Path, artifacts: list[Artifact], work: Path, subject: Path, expectations: dict,
          exec_ok: bool, run: Runner = subprocess.run, tree_hook: TreeHook | None = None,
          manifests: dict | None = None, xvfb: bool = True) -> list[Record]:
    settings = expectations["linux"]
    records = []
    for artifact in artifacts:
        folder = artifacts_dir / artifact.name
        files = sorted(p for p in folder.iterdir() if p.is_file()) if folder.is_dir() else []
        if not files:
            records.append(Record("linux", artifact.name, "", "elf", "fail", "artifact was not downloaded or is empty"))
            continue
        if artifact.kind == "elf":
            expected = artifact.spec.get("elf_arch", "x86_64")
            fmt = binfmt.detect(files[0])
            status = "pass" if fmt and fmt.archs == [expected] else "fail"
            found = " ".join(fmt.archs) if fmt else "not an ELF file"
            records.append(Record("linux", artifact.name, files[0].name, "elf", status, f"{found}, expected {expected}"))
            continue
        appimage = files[0]
        if artifact.arch != "x86_64":
            fmt = binfmt.detect(appimage)
            ok = fmt is not None and fmt.archs == [artifact.arch]
            records.append(Record("linux", artifact.name, appimage.name, "elf", "pass" if ok else "fail",
                                  f"runtime ELF machine {' '.join(fmt.archs) if fmt else 'none'}, expected {artifact.arch}"))
            for check_name in ("smoke", "slice"):
                records.append(Record("linux", artifact.name, "", check_name, "skip",
                                      f"{artifact.arch} AppImage is not run on the x64 runner", {"by_design": True}))
            continue
        root, why = extract(appimage, work / artifact.name, exec_ok, run)
        if root is None:
            records.append(Record("linux", artifact.name, appimage.name, "elf", "fail", f"could not unpack: {why}"))
            continue
        records += elf_records(artifact.name, root, "x86_64")
        if manifests is not None:
            manifests[artifact.name] = build_manifest(root)
        resources = find_resources(root)
        if tree_hook:
            records += tree_hook(artifact, root)
        if not exec_ok:
            for check_name in ("smoke", "slice"):
                records.append(Record("linux", artifact.name, "", check_name, "skip",
                                      "built from a fork: never executed (0141)", {"by_design": True}))
            continue
        app_run = root / "AppRun"
        records.append(smoke(artifact.name, app_run, settings["smoke_timeout"], run, xvfb))
        if resources is None:
            records.append(Record("linux", artifact.name, "", "slice", "fail", "no resources folder in the AppImage"))
        else:
            records.append(slicer.run_slice(artifact.name, app_run, resources, subject, work / artifact.name,
                                            expectations, run, xvfb))
    return records
