"""Derive branding rasters (PNG, ICO, ICNS) from their SVG master, as listed in derived-assets.toml.

    python scripts/cosmyx/branding/derive/derive.py write --docker   # re-render, rewrite only changed outputs
    python scripts/cosmyx/branding/derive/derive.py check --docker   # exit 1 and list outputs that differ
    python scripts/cosmyx/branding/derive/derive.py stable --docker  # render twice, exit 1 if the runs differ

Rendering uses the resvg of the pinned image (Dockerfile in this folder, linux/amd64): `--docker` builds it if
needed and runs this script inside it. Without `--docker` resvg must be on PATH, which is only the case inside
that image. Use the recipes (`just brand-derive`, `just brand-derive-check`, `just brand-derive-stable`).

Outputs land in the branding overlay; their manifest rows are then refreshed by `just brand-refresh PATH`
(status to-validate). Decisions 0124-0126.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

if __package__ in (None, ""):
    # Run as a script: make the branding package importable from scripts/cosmyx.
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from branding.derive import icns, ico, raster  # noqa: E402

MODULE_DIR = Path(__file__).resolve().parent
MANIFEST = MODULE_DIR / "derived-assets.toml"
DOCKERFILE = MODULE_DIR / "Dockerfile"
REPO_ROOT = MODULE_DIR.parents[3]
FORMATS = ("png", "ico", "icns")
KEYS = {"source", "output", "format", "size", "grayscale"}
PLATFORM = "linux/amd64"
MOUNT_POINT = "/repo"
IMAGE_NAME = "cosmyx-resvg"

Renderer = Callable[[Path, int], bytes]


class ResvgMissingError(RuntimeError):
    """resvg is not on PATH: the command was run outside the pinned image."""


class RenderError(RuntimeError):
    """resvg failed on a source; the message carries the source path and resvg's stderr."""


@dataclass(frozen=True)
class Entry:
    source: str
    output: str
    format: str
    size: int | tuple[int, ...] | None
    grayscale: bool = False


def _relative_posix(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    if "\\" in value:
        raise ValueError(f"{field} '{value}' must use POSIX '/' separators")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise ValueError(f"{field} '{value}' must be relative to the repository root, without '..'")
    return path.as_posix()


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _entry(raw: object, root: Path) -> Entry:
    if not isinstance(raw, Mapping):
        raise ValueError("must be a table ([[derived]])")
    unknown = sorted(set(raw) - KEYS)
    if unknown:
        raise ValueError(f"unknown keys {unknown}")
    source = _relative_posix(raw.get("source"), "source")
    output = _relative_posix(raw.get("output"), "output")
    if source == output:
        raise ValueError(f"output '{output}' is its own source")
    fmt = raw.get("format")
    if fmt not in FORMATS:
        raise ValueError(f"format {fmt!r} must be one of {FORMATS}")
    size = raw.get("size")
    grayscale = raw.get("grayscale", False)
    if not isinstance(grayscale, bool):
        raise ValueError(f"grayscale of '{output}' must be true or false")
    if grayscale and fmt != "png":
        raise ValueError(f"grayscale only applies to png outputs, not '{output}'")
    if fmt == "png":
        if not _positive_int(size):
            raise ValueError(f"png output '{output}' needs a positive integer size")
    elif fmt == "ico":
        if not isinstance(size, list) or not size or not all(_positive_int(s) and s <= 256 for s in size):
            raise ValueError(f"ico output '{output}' needs a list of sizes from 1 to 256")
        if len(set(size)) != len(size):
            raise ValueError(f"ico output '{output}' lists a size twice")
        size = tuple(sorted(size))
    elif size is not None:
        raise ValueError(f"icns output '{output}' takes no size (it holds every icon size)")
    if not (root / source).is_file():
        raise ValueError(f"source '{source}' does not exist")
    return Entry(source, output, fmt, size, grayscale)


def load_manifest(manifest: Path = MANIFEST, root: Path = REPO_ROOT) -> list[Entry]:
    """Validated entries of the manifest, in file order."""
    import tomllib  # Python 3.11+, only needed here.

    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    derived = data.get("derived", [])
    if not isinstance(derived, list):
        raise ValueError(f"{manifest.name}: derived must be an array of tables ([[derived]])")
    entries = []
    for index, raw in enumerate(derived):
        try:
            entries.append(_entry(raw, root))
        except ValueError as error:
            raise ValueError(f"{manifest.name} entry {index + 1}: {error}") from error
    outputs = [entry.output for entry in entries]
    duplicates = sorted({o for o in outputs if outputs.count(o) > 1})
    if duplicates:
        raise ValueError(f"{manifest.name}: duplicate outputs {duplicates}")
    sources = {entry.source for entry in entries}
    if sources & set(outputs):
        raise ValueError(f"{manifest.name}: outputs used as sources {sorted(sources & set(outputs))}")
    return entries


def find_resvg() -> str:
    path = shutil.which("resvg")
    if path is None:
        raise ResvgMissingError(
            "resvg not found: run through `just brand-derive` (or derive.py --docker), which uses the pinned image"
        )
    return path


def resvg_renderer(command: Sequence[str] | None = None) -> Renderer:
    """Renderer that rasterises an SVG to a square PNG of `size` px with the pinned resvg.

    `command` replaces the resvg invocation (its arguments are appended); RenderError when it fails.
    """
    base = list(command) if command is not None else [find_resvg()]

    def render(source: Path, size: int) -> bytes:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.png"
            try:
                subprocess.run(
                    [*base, "-w", str(size), "-h", str(size), str(source), str(out)],
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as error:
                stderr = error.stderr.decode("utf-8", errors="replace").strip() if error.stderr else ""
                raise RenderError(
                    f"resvg failed on {source} at {size} px (exit status {error.returncode}): {stderr or 'no output'}"
                ) from error
            return out.read_bytes()

    return render


def render_entry(entry: Entry, root: Path, render: Renderer) -> bytes:
    """Bytes of one output, freshly rendered from its source."""
    source = root / entry.source
    if entry.format == "png":
        if not isinstance(entry.size, int):
            raise ValueError(f"png output '{entry.output}' has no size")
        data = render(source, entry.size)
        return raster.encode(raster.grayscale(raster.decode(data))) if entry.grayscale else data
    if entry.format == "ico":
        if not isinstance(entry.size, tuple):
            raise ValueError(f"ico output '{entry.output}' has no sizes")
        return ico.write_ico({size: render(source, size) for size in entry.size})
    return icns.write_icns({size: render(source, size) for size in icns.REQUIRED_SIZES})


def write(entries: Iterable[Entry], root: Path, render: Renderer) -> list[str]:
    """Render every entry; rewrite (in place) only the outputs whose bytes changed. Returns those outputs."""
    changed = []
    for entry in entries:
        data = render_entry(entry, root, render)
        target = root / entry.output
        if target.is_file() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        # Overwrite in place: the folder is never deleted or recreated (SMB share).
        with target.open("wb") as handle:
            handle.write(data)
        changed.append(entry.output)
    return changed


def check(entries: Iterable[Entry], root: Path, render: Renderer) -> list[str]:
    """Outputs that are missing or differ from a fresh render."""
    stale = []
    for entry in entries:
        target = root / entry.output
        if not target.is_file() or target.read_bytes() != render_entry(entry, root, render):
            stale.append(entry.output)
    return stale


def stable(entries: Iterable[Entry], root: Path, render: Renderer) -> list[str]:
    """Outputs whose two consecutive renders differ."""
    return [e.output for e in entries if render_entry(e, root, render) != render_entry(e, root, render)]


# ---------------------------------------------------------------- pinned image


def image_tag(dockerfile: Path = DOCKERFILE) -> str:
    """Local tag of the pinned image: a hash of its Dockerfile, so an edit rebuilds it."""
    digest = hashlib.sha256(dockerfile.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16]
    return f"{IMAGE_NAME}:{digest}"


# Architectures `docker info` reports for a daemon that runs linux/amd64 natively.
NATIVE_AMD64 = frozenset({"x86_64", "amd64"})


def probe_image(dockerfile: Path = DOCKERFILE) -> str:
    """The digest-pinned base image of the final stage, the smallest image the render needs anyway."""
    images = [line.split()[1] for line in dockerfile.read_text(encoding="utf-8").splitlines() if line.startswith("FROM ")]
    if not images:
        raise ValueError(f"{dockerfile} has no FROM line")
    return images[-1]


def emulation_unavailable(dockerfile: Path = DOCKERFILE) -> str | None:
    """Why a non-amd64 daemon cannot run linux/amd64 containers (no binfmt emulation), or None when it can."""
    result = subprocess.run(
        ["docker", "run", "--rm", "--platform", PLATFORM, probe_image(dockerfile), "true"],
        capture_output=True, text=True, check=False,
    )  # fmt: skip
    if result.returncode == 0:
        return None
    detail = (result.stderr or result.stdout).strip().splitlines()
    return f"the docker daemon cannot run {PLATFORM} containers ({detail[-1] if detail else 'exit ' + str(result.returncode)})"


def docker_unavailable(dockerfile: Path = DOCKERFILE) -> str | None:
    """Why the pinned linux/amd64 image cannot run here, or None when it can.

    On a daemon that is not amd64 (an arm64 runner, Apple silicon) one tiny container is started to check
    that linux/amd64 emulation works, so a missing emulator is reported here instead of failing the build.
    """
    if shutil.which("docker") is None:
        return "docker is not installed"
    result = subprocess.run(
        ["docker", "info", "--format", "{{.OSType}} {{.Architecture}}"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        return "the docker daemon is not reachable"
    fields = result.stdout.split()
    os_type = fields[0] if fields else ""
    architecture = fields[1] if len(fields) > 1 else ""
    if os_type != "linux":
        return f"docker runs {os_type or 'unknown'} containers, not linux"
    if architecture.lower() in NATIVE_AMD64:
        return None
    return emulation_unavailable(dockerfile)


def ensure_image(dockerfile: Path = DOCKERFILE) -> str:
    """Build the pinned image if this Dockerfile has not been built yet; return its tag."""
    tag = image_tag(dockerfile)
    present = subprocess.run(
        ["docker", "image", "inspect", tag], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
    )
    if present.returncode != 0:
        # No build context: the Dockerfile copies nothing from the tree.
        subprocess.run(
            ["docker", "build", "--platform", PLATFORM, "--tag", tag, "-"], input=dockerfile.read_bytes(), check=True
        )
    return tag


def user_args() -> list[str]:
    """Run as the host user where the host has POSIX ids, so written files keep their owner."""
    getuid = getattr(os, "getuid", None)
    getgid = getattr(os, "getgid", None)
    if getuid is None or getgid is None:
        return []
    return ["--user", f"{getuid()}:{getgid()}"]


def docker_command(tag: str, mode: str, root: Path = REPO_ROOT) -> list[str]:
    """docker run command that runs this script in `mode` inside the pinned image, the tree mounted at /repo."""
    script = PurePosixPath(MOUNT_POINT, *Path(__file__).resolve().relative_to(root).parts)
    return [
        "docker", "run", "--rm", "--platform", PLATFORM,
        "--mount", f"type=bind,source={root},target={MOUNT_POINT}",
        "--workdir", MOUNT_POINT, "--env", "HOME=/tmp",
        *user_args(), tag, "python", str(script), mode,
    ]  # fmt: skip


def run_in_docker(mode: str, root: Path = REPO_ROOT, capture: bool = False) -> subprocess.CompletedProcess:
    """Run `derive.py <mode>` inside the pinned image."""
    reason = docker_unavailable()
    if reason:
        raise ResvgMissingError(f"cannot run the pinned image: {reason}")
    return subprocess.run(docker_command(ensure_image(), mode, root), capture_output=capture, text=True, check=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("write", "check", "stable"))
    parser.add_argument("--docker", action="store_true", help="run inside the pinned resvg image")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if args.docker:
        try:
            return run_in_docker(args.mode).returncode
        except (ResvgMissingError, subprocess.CalledProcessError) as error:
            print(f"derive.py: {error}", file=sys.stderr)
            return 2
    try:
        render = resvg_renderer()
    except ResvgMissingError as error:
        print(f"derive.py: {error}", file=sys.stderr)
        return 2
    entries = load_manifest()
    if args.mode == "write":
        for output in write(entries, REPO_ROOT, render):
            print(f"rewrote {output}")
        print("then: just brand-refresh PATH for each rewritten output (rows go back to to-validate)")
        return 0
    if args.mode == "check":
        stale = check(entries, REPO_ROOT, render)
        for output in stale:
            print(f"stale: {output} (run `just brand-derive`)", file=sys.stderr)
        print(f"derive check: {len(entries)} outputs, {len(stale)} stale")
        return 1 if stale else 0
    unstable = stable(entries, REPO_ROOT, render)
    for output in unstable:
        print(f"unstable: {output} (two renders differ)", file=sys.stderr)
    print(f"derive stable: {len(entries)} outputs rendered twice, {len(unstable)} differ")
    return 1 if unstable else 0


if __name__ == "__main__":
    sys.exit(main())
