"""Starting the built application for a pass (decision 0170).

- Linux: the AppImage is extracted (--appimage-extract) and AppRun started
  under Xvfb 1600x1000x24 with openbox, when no display is set (the Docker
  image).
- macOS: the .app is copied out of the DMG, so the mounted image can go.
- Windows: the portable build is copied to a temporary folder and the pinned
  Mesa software renderer (artifact_checks.mesa_win, decision 0161) is fetched
  into its mesa/ folder, then its DLLs are copied next to the executable.
  The launcher's --sw-renderer switch cannot be used: it is passed on to the
  command line parser, which rejects it (its option is commented out in
  PrintConfig.cpp). opengl32.dll is not a known DLL, so the copy next to the
  executable wins over the system one, and the launcher's own OpenGL check
  then sees Mesa.

Every OS gets --datadir <seeded folder> and the COSMYX_GUI_DRIVER_* variables.
"""

from __future__ import annotations

import os
import plistlib
import shutil
import subprocess
import time
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import GoldenError

Runner = Callable[..., subprocess.CompletedProcess]
SCREEN = "1600x1000x24"
DISPLAY = ":99"


@dataclass
class App:
    command: list[str]
    process: str
    env: dict[str, str] = field(default_factory=dict)


def _one(paths: list[Path], what: str) -> Path:
    if len(paths) != 1:
        raise GoldenError(f"expected one {what}, found {len(paths)}: {[p.name for p in paths]}")
    return paths[0]


def prepare_linux(artifact_dir: Path, work: Path, run: Runner = subprocess.run) -> App:
    appimage = _one(sorted(artifact_dir.rglob("*.AppImage")), "AppImage")
    work.mkdir(parents=True, exist_ok=True)
    local = work / appimage.name
    shutil.copy2(appimage, local)
    local.chmod(0o755)
    done = run([str(local), "--appimage-extract"], cwd=work, capture_output=True, text=True, check=False)
    app_run = work / "squashfs-root" / "AppRun"
    if done.returncode != 0 or not app_run.is_file():
        raise GoldenError(f"--appimage-extract failed ({done.returncode})")
    return App([str(app_run)], "orca-slicer")


def find_app(root: Path) -> Path:
    apps = [p for p in sorted(root.glob("*.app")) if "profile_validator" not in p.name]
    return _one(apps, ".app bundle")


def prepare_macos(artifact_dir: Path, work: Path, run: Runner = subprocess.run) -> App:
    dmg = _one(sorted(p for p in artifact_dir.rglob("*.dmg") if "profile_validator" not in p.name), "DMG")
    mount = work / "mount"
    mount.mkdir(parents=True, exist_ok=True)
    attach = run(["hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen", "-mountpoint", str(mount), str(dmg)],
                 capture_output=True, text=True, check=False)
    if attach.returncode != 0:
        raise GoldenError(f"hdiutil attach failed: {attach.stderr.strip()}")
    try:
        source = find_app(mount)
        target = work / source.name
        if target.exists():
            shutil.rmtree(target)
        copied = run(["ditto", str(source), str(target)], capture_output=True, text=True, check=False)
        if copied.returncode != 0:
            raise GoldenError(f"ditto failed: {copied.stderr.strip()}")
    finally:
        if run(["hdiutil", "detach", str(mount)], capture_output=True, check=False).returncode != 0:
            run(["hdiutil", "detach", "-force", str(mount)], capture_output=True, check=False)
    info = plistlib.loads((target / "Contents" / "Info.plist").read_bytes())
    executable = info.get("CFBundleExecutable", "OrcaSlicer")
    return App([str(target / "Contents" / "MacOS" / executable)], executable)


def mesa_fetch(dest: Path) -> tuple[Path, dict[str, str]]:
    """artifact_checks.mesa_win (T16a): fetches the pinned Mesa into `dest`
    (a folder named mesa) and gives the environment the app needs (Mesa first
    on PATH, GALLIUM_DRIVER=llvmpipe). Imported from the trusted checkout only
    when a Windows pass runs."""
    from artifact_checks import inventory, mesa_win  # noqa: PLC0415 (runtime import, decision 0161)
    folder = Path(mesa_win.fetch(dest))
    env = mesa_win.run_env(dict(os.environ), folder, mesa_win.load_pin(inventory.load_expectations()))
    return folder, dict(env)


# The Windows exe names, branded first: CosmoSlice.exe once the package-name
# branding renames it, orca-slicer.exe / OrcaSlicer.exe for older builds.
WINDOWS_EXES = ("CosmoSlice.exe", "orca-slicer.exe", "OrcaSlicer.exe")


def find_windows_exes(root: Path) -> list[Path]:
    """Every copy of the first exe name of WINDOWS_EXES found under `root`."""
    for name in WINDOWS_EXES:
        exes = sorted(root.rglob(name))
        if exes:
            return exes
    return []


def prepare_windows(artifact_dir: Path, work: Path,
                    fetch: Callable[[Path], tuple[Path, dict[str, str]]] = mesa_fetch) -> App:
    exes = find_windows_exes(artifact_dir)
    app_dir = work / "app"
    if app_dir.exists():
        shutil.rmtree(app_dir)
    if not exes:
        archive = _one(sorted(artifact_dir.rglob("*.zip")), "portable zip")
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(work / "unzipped")
        exes = find_windows_exes(work / "unzipped")
    source = _one(exes, " or ".join(WINDOWS_EXES))
    shutil.copytree(source.parent, app_dir)
    exe = app_dir / source.name
    fetched, env = fetch(app_dir / "mesa")
    dll_dir = fetched.parent if fetched.is_file() else fetched
    if not (dll_dir / "opengl32.dll").is_file() or dll_dir.resolve() != (app_dir / "mesa").resolve():
        raise GoldenError(f"Mesa was not put in {app_dir / 'mesa'} (got {fetched})")
    for dll in sorted(dll_dir.glob("*.dll")):
        shutil.copy2(dll, exe.parent / dll.name)
    return App([str(exe)], exe.stem, env)


def prepare(os_name: str, artifact_dir: Path, work: Path) -> App:
    if os_name == "linux":
        return prepare_linux(artifact_dir, work)
    if os_name == "macos":
        return prepare_macos(artifact_dir, work)
    if os_name == "windows":
        return prepare_windows(artifact_dir, work)
    raise GoldenError(f"unknown OS {os_name!r}")


def driver_env(base: dict[str, str], driver_dir: Path, script: Path, os_name: str) -> dict[str, str]:
    env = dict(base)
    env.update({"COSMYX_GUI_DRIVER_DIR": str(driver_dir), "COSMYX_GUI_DRIVER_SCRIPT": str(script),
                "COSMYX_GUI_DRIVER_OS": os_name, "LANG": "en_US.UTF-8", "LC_ALL": "en_US.UTF-8", "TZ": "UTC"})
    return env


def command(app: App, datadir: Path) -> list[str]:
    return app.command + ["--datadir", str(datadir)]


def start_display(env: dict[str, str], popen=subprocess.Popen, sleep=time.sleep) -> list[subprocess.Popen]:
    """Xvfb and openbox for a Linux pass with no display (openbox: dialogs
    and menus need a window manager to be placed and focused)."""
    if env.get("DISPLAY"):
        return []
    env["DISPLAY"] = DISPLAY
    xvfb = popen(["Xvfb", DISPLAY, "-screen", "0", SCREEN, "-nolisten", "tcp", "-noreset"], env=env)
    sleep(1.0)
    wm = popen(["openbox"], env=env)
    sleep(1.0)
    return [xvfb, wm]


def start_display_for(os_name: str, env, popen=subprocess.Popen, sleep=time.sleep) -> list[subprocess.Popen]:
    """Only Linux passes need their own display; Windows and macOS runners
    have a desktop session."""
    return start_display(env, popen, sleep) if os_name == "linux" else []


def start(app: App, datadir: Path, driver_dir: Path, script: Path, os_name: str, log: Path,
          popen=subprocess.Popen) -> subprocess.Popen:
    env = driver_env({**os.environ, **app.env}, driver_dir, script, os_name)
    handle = log.open("wb")
    return popen(command(app, datadir), env=env, stdout=handle, stderr=subprocess.STDOUT)


def stop(process: subprocess.Popen, timeout: float = 10.0) -> None:
    if process.poll() is None:
        process.kill()
        try:
            process.wait(timeout)
        except subprocess.TimeoutExpired:
            pass
