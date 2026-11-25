"""Pinned Mesa software OpenGL for the Windows runs (decision 0161).

Hosted Windows runners have no GPU, and the default opengl32.dll only offers
OpenGL 1.1. The app's Windows launcher (OrcaSlicer_app_msvc.cpp) then loads
<exe folder>/mesa/opengl32.dll, which the build does not ship. This module
fetches one pinned mesa-dist-win release (MIT), checks its SHA-256 and the
SHA-256 of every file it takes, and puts those files in the mesa/ folder of a
temporary copy of the portable app and next to its exe. Mesa is test-only: it never reaches an
artifact.

The archive is 7z: Python cannot read it, so the runner's 7-Zip unpacks it.
Without 7-Zip the runs are skipped with that reason; a hash mismatch fails.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .policy_windows import find_seven_zip

Runner = Callable[..., subprocess.CompletedProcess]
Opener = Callable[..., object]
CACHE_ENV = "COSMYX_MESA_CACHE"
DOWNLOAD_ATTEMPTS = 3


class MesaError(Exception):
    """Mesa could not be prepared. status is "skip" (a tool is missing) or
    "fail" (download or integrity problem)."""

    def __init__(self, status: str, reason: str) -> None:
        super().__init__(reason)
        self.status, self.reason = status, reason


@dataclass
class Pin:
    version: str
    url: str
    sha256: str
    files: dict[str, str]  # archive member (POSIX) -> SHA-256
    env: dict[str, str] = field(default_factory=dict)

    @property
    def asset(self) -> str:
        return PurePosixPath(self.url).name


@dataclass
class Prepared:
    mesa_dir: Path
    env: dict[str, str]
    details: dict


def load_pin(expectations: dict) -> Pin:
    data = expectations["mesa_win"]
    return Pin(data["version"], data["url"], data["sha256"].lower(),
               {name: digest.lower() for name, digest in data["files"].items()}, dict(data.get("env", {})))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url: str, target: Path, opener: Opener = urllib.request.urlopen, attempts: int = DOWNLOAD_ATTEMPTS,
             pause: float = 5.0) -> None:
    """Download url to target (through a .part file), retrying network errors."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    last = ""
    for attempt in range(1, attempts + 1):
        try:
            with opener(url, timeout=120) as response, open(partial, "wb") as out:
                shutil.copyfileobj(response, out, 1 << 20)
            os.replace(partial, target)
            return
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            last = str(error)
            partial.unlink(missing_ok=True)
            if attempt < attempts:
                time.sleep(pause)
    raise MesaError("fail", f"could not download Mesa {url} after {attempts} attempts: {last}")


def archive_path(pin: Pin, work: Path, env: dict) -> Path:
    cache = env.get(CACHE_ENV, "").strip()
    return (Path(cache) if cache else work / "mesa-download") / pin.asset


def fetch_archive(pin: Pin, work: Path, env: dict, opener: Opener = urllib.request.urlopen,
                  pause: float = 5.0) -> Path:
    """The pinned archive, from the cache when its hash matches, else downloaded.
    A downloaded archive with another hash fails (and is deleted)."""
    archive = archive_path(pin, work, env)
    if archive.is_file() and sha256_file(archive) == pin.sha256:
        return archive
    download(pin.url, archive, opener, pause=pause)
    found = sha256_file(archive)
    if found != pin.sha256:
        archive.unlink(missing_ok=True)
        raise MesaError("fail", f"Mesa archive SHA-256 {found}, pinned {pin.sha256}")
    return archive


def extract_command(seven_zip: str, archive: Path, target: Path, pin: Pin) -> list[str]:
    """7-Zip `e` (no folders): the pinned files land directly in target."""
    return [seven_zip, "e", "-y", f"-o{target}", str(archive), *sorted(pin.files)]


def extract(seven_zip: str, archive: Path, target: Path, pin: Pin, run: Runner = subprocess.run) -> dict[str, Path]:
    """Unpack the pinned files into target and check each one's SHA-256."""
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    done = run(extract_command(seven_zip, archive, target, pin), capture_output=True, text=True, errors="replace",
               check=False)
    if done.returncode != 0:
        tail = (done.stderr or done.stdout or "").strip().splitlines()[-1:]
        raise MesaError("fail", f"7-Zip could not unpack Mesa (exit {done.returncode}) {' '.join(tail)}".strip())
    files = {}
    for member, expected in sorted(pin.files.items()):
        path = target / PurePosixPath(member).name
        if not path.is_file():
            raise MesaError("fail", f"Mesa archive has no {member}")
        found = sha256_file(path)
        if found != expected:
            raise MesaError("fail", f"Mesa {member} SHA-256 {found}, pinned {expected}")
        files[member] = path
    return files


def run_env(base: dict, mesa_dir: Path, pin: Pin) -> dict[str, str]:
    """The app's environment: Mesa's folder first on PATH, so opengl32.dll
    finds libgallium_wgl.dll next to it, plus the pinned driver variables."""
    env = dict(base)
    key = next((k for k in env if k.upper() == "PATH"), "PATH")
    env[key] = os.pathsep.join(p for p in (str(mesa_dir), env.get(key, "")) if p)
    env.update(pin.env)
    return env


def prepare(app_dir: Path, work: Path, expectations: dict, env: dict, run: Runner = subprocess.run,
            opener: Opener = urllib.request.urlopen, seven_zip: str | None = None, pause: float = 5.0) -> Prepared:
    """Put the pinned Mesa files in app_dir/mesa/ and return the app's environment.
    Raises MesaError."""
    pin = load_pin(expectations)
    seven_zip = seven_zip if seven_zip is not None else (find_seven_zip(env) or "")
    if not seven_zip:
        raise MesaError("skip", "7-Zip not found: the pinned Mesa archive (7z) cannot be unpacked")
    archive = fetch_archive(pin, work, env, opener, pause)
    files = extract(seven_zip, archive, work / "mesa-extract", pin, run)
    mesa_dir = app_dir / "mesa"
    mesa_dir.mkdir(parents=True, exist_ok=True)
    for path in files.values():
        shutil.copy2(path, mesa_dir / path.name)
        # Also next to the exe: the launcher's version check loads
        # "opengl32.dll" by name (the exe folder is searched first, it is not
        # a KnownDLL), so it finds OpenGL >= 2.0 and the app imports this one.
        shutil.copy2(path, app_dir / path.name)
    details = {"mesa": pin.version, "mesa_sha256": pin.sha256, "mesa_files": sorted(p.name for p in files.values())}
    return Prepared(mesa_dir, run_env(env, mesa_dir, pin), details)


def fetch(mesa_dir: Path, work: Path | None = None, env: dict | None = None, **kwargs) -> Path:
    """Put the pinned Mesa files directly in mesa_dir (<app folder>/mesa) and
    return it. The app still needs run_env() (PATH and GALLIUM_DRIVER).
    Raises MesaError. Used by the GUI goldens launcher."""
    from .inventory import load_expectations

    mesa_dir = Path(mesa_dir)
    if mesa_dir.name != "mesa":
        raise ValueError(f"{mesa_dir} must be the app's mesa folder")
    work = Path(work) if work is not None else mesa_dir.parent.parent / "mesa-work"
    env = dict(os.environ if env is None else env)
    return prepare(mesa_dir.parent, work, load_expectations(), env, **kwargs).mesa_dir
