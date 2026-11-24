"""Give the CI packages and artifacts their CosmoSlice names (decision 0210).

    python scripts/cosmyx/package_names.py <stage> [--root DIR] [--output FILE]

The pre-build branding (cosmyx-prepare) renames what the build itself names:
the Windows executable and installer, the AppImage launcher. What only the
workflow names (its upload steps, read before checkout, so the branding cannot
patch them) is renamed here, by the `cosmyx-package-names` action that the
`# Cosmyx` hook steps of build_orca.yml and build_flatpak.yml call:

- `mac-app` (after "Create DMG without notary", before the Cosmyx signing):
  renames the universal `OrcaSlicer.app` to `CosmoSlice.app`, drops the
  profile validator app and DMG, drops the unsigned `OrcaSlicer_` DMG and
  builds `CosmoSlice_Mac_universal_<ver>.dmg` (volume CosmoSlice) with
  upstream's scripts/create_dmg.sh. The signing, when on, signs every app of
  the folder and rebuilds the DMG under the app's name, so it keeps this name.
  A pull-request leg builds no universal app and ships its arch's own DMG
  (upstream's "Create DMG <arch> without notary", before this hook): the stage
  does the same there, `CosmoSlice_Mac_<arch>_<ver>.dmg` from `CosmoSlice.app`.
- `mac-upload` (after the upstream mac uploads): uploads that DMG and deletes
  the `OrcaSlicer_Mac_` artifact it replaces.
- `windows` (after "Build MSIX Store package Win"): renames the MSIX, uploads
  the portable folder, the installer and the MSIX under CosmoSlice names.
- `linux` (before "Upload artifacts Ubuntu"): renames the AppImage and
  uploads it; drops the profile validator binary, so the upstream step after
  it uploads nothing.
- `flatpak` (before "Upload artifacts Flatpak"): renames the bundle and
  uploads it.

Every stage also lists the upstream `OrcaSlicer_` artifacts it replaces and
the profile validator artifacts, which the action deletes: a Cosmyx build
exports neither. A stage that does not apply to the running leg (another OS,
a macOS push leg that only packs its bundle, a leg that built no MSIX) does nothing.

The names come from cosmyx-src/branding/product-name/packages.json. Each
template renders with `{product}` (CosmoSlice) and `{upstream}` (OrcaSlicer),
and the job's `ver`, arch suffix and Ubuntu version, read from the COSMYX_PKG_*
variables the action sets. The outputs go to $GITHUB_OUTPUT (or --output):
`<package>_name` and `<package>_path` per upload, and `delete` (one artifact
name per line). Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TABLE = "cosmyx-src/branding/product-name/packages.json"
STAGES = ("mac-app", "mac-upload", "windows", "linux", "flatpak")
# RUNNER_ARCH -> the arch the Flatpak bundle names.
FLATPAK_ARCH = {"X64": "x86_64", "ARM64": "aarch64"}
# The archs a macOS pull-request leg may build (build_all.yml), each its own DMG.
MAC_ARCHS = ("arm64", "x86_64")


class PackageError(Exception):
    pass


def load_table(root: Path = REPO_ROOT) -> dict:
    data = json.loads((root / TABLE).read_bytes().decode("utf-8"))
    if data.get("schema") != 1:
        raise PackageError(f"{TABLE}: schema must be 1")
    for key in ("upstream", "product"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise PackageError(f"{TABLE}: {key} must be a non-empty string")
    return data


class Names:
    """Render the templates of one section for the product or for upstream."""

    def __init__(self, table: dict, section: str, **fields: str) -> None:
        self.templates = table[section]
        self.fields = dict(fields, upstream=table["upstream"])
        self.product = table["product"]
        self.upstream = table["upstream"]

    def new(self, key: str) -> str:
        return self.templates[key].format(product=self.product, **self.fields)

    def old(self, key: str) -> str:
        return self.templates[key].format(product=self.upstream, **self.fields)


def env_value(env: dict, name: str, required: bool = True) -> str:
    value = env.get(f"COSMYX_PKG_{name}", "")
    if required and not value:
        raise PackageError(f"COSMYX_PKG_{name} is not set")
    return value


def remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def empty_folder(folder: Path) -> None:
    """Empty a folder in place, never delete and recreate it (SMB rule)."""
    folder.mkdir(parents=True, exist_ok=True)
    for child in folder.iterdir():
        remove(child)


def run_bash(command: str) -> None:
    subprocess.run(["bash", "-c", command], check=True)


def build_dmg(root: Path, app: Path, staging: Path, volume: str, output: Path, runner=run_bash) -> None:
    """Upstream's DMG layout: the app (copied with ditto, which keeps the bundle's
    links, modes and extended attributes) and an /Applications link, made into a
    DMG by scripts/create_dmg.sh."""
    empty_folder(staging)
    scripts = root / "scripts"
    q = lambda path: shlex.quote(str(path))  # noqa: E731
    runner(
        f"set -e; ditto {q(app)} {q(staging / app.name)}; ln -s /Applications {q(staging / 'Applications')}; "
        f"source {q(scripts / 'retry.sh')}; source {q(scripts / 'create_dmg.sh')}; "
        f"create_dmg {shlex.quote(volume)} {q(staging)} {q(output)}"
    )


# ---------------------------------------------------------------- stages


def mac_leg(table: dict, workspace: Path, env: dict) -> Names | None:
    """The macOS leg's names, with `{arch}` set to what it ships: `universal` on
    the combine job, the arch on a pull-request leg (which ships its own DMG,
    `{upstream}_Mac_<arch>_<ver>.dmg`, or the CosmoSlice one on a rerun), None
    on a push leg, which only packs its bundle for the combine job."""
    ver = env_value(env, "VER")
    names = Names(table, "mac", ver=ver, arch="universal")
    if (workspace / names.new("bundle_dir")).is_dir():
        return names
    for arch in MAC_ARCHS:
        names = Names(table, "mac", ver=ver, arch=arch)
        if (workspace / names.new("bundle_dir")).is_dir() and (
            (workspace / names.old("dmg")).is_file() or (workspace / names.new("dmg")).is_file()
        ):
            return names
    return None


def stage_mac_app(table: dict, root: Path, workspace: Path, env: dict, runner=run_bash) -> dict:
    if env.get("RUNNER_OS") != "macOS":
        return {}
    names = mac_leg(table, workspace, env)
    if names is None:
        return {}
    folder = workspace / names.new("bundle_dir")
    old_app, new_app = folder / names.old("app"), folder / names.new("app")
    if old_app.exists():
        if new_app.exists():
            raise PackageError(f"both {old_app.name} and {new_app.name} are in {folder}")
        old_app.rename(new_app)
    elif not new_app.is_dir():
        raise PackageError(f"no {old_app.name} in {folder}")
    remove(folder / names.new("validator_app"))
    remove(workspace / names.new("validator_dmg"))
    remove(workspace / names.old("dmg"))
    build_dmg(root, new_app, workspace / names.new("dmg_staging"), names.new("volume"), workspace / names.new("dmg"), runner)
    return {}


def stage_mac_upload(table: dict, root: Path, workspace: Path, env: dict, runner=run_bash) -> dict:
    if env.get("RUNNER_OS") != "macOS":
        return {}
    names = mac_leg(table, workspace, env)
    if names is None:
        return {}
    dmg = workspace / names.new("dmg")
    if not dmg.is_file():
        raise PackageError(f"{dmg.name} is missing: the mac-app stage did not run before this one")
    delete = [names.old("artifact")]
    if names.fields["arch"] == "universal":
        delete.append(names.new("validator_artifact"))
    return {"dmg_name": names.new("artifact"), "dmg_path": str(dmg), "delete": delete}


def stage_windows(table: dict, root: Path, workspace: Path, env: dict, runner=run_bash) -> dict:
    if env.get("RUNNER_OS") != "Windows":
        return {}
    names = Names(table, "windows", ver=env_value(env, "VER"), arch=env_value(env, "ARCH", required=False))
    build = workspace / env_value(env, "BUILD_DIR")
    portable = build / names.templates["portable_dir"]
    if not portable.is_dir():
        raise PackageError(f"no portable folder {portable}")
    outputs = {
        "portable_name": names.new("portable_artifact"),
        "portable_path": str(portable),
        "delete": [names.old("portable_artifact"), names.old("installer_artifact"), names.new("validator_artifact")],
    }
    stale = sorted(build.glob(names.old("installer_glob")))
    if stale:
        raise PackageError(f"{stale[0].name}: the installer kept its upstream name, the branding did not rename it")
    installers = sorted(build.glob(names.new("installer_glob")))
    if len(installers) > 1:
        raise PackageError(f"several installers in {build}: {', '.join(path.name for path in installers)}")
    if installers:
        outputs.update(installer_name=names.new("installer_artifact"), installer_path=str(installers[0]))
    old_msix, new_msix = build / names.old("msix"), build / names.new("msix")
    if old_msix.is_file():
        old_msix.replace(new_msix)
    if new_msix.is_file():
        outputs.update(msix_name=names.new("msix_artifact"), msix_path=str(new_msix))
        outputs["delete"].append(names.old("msix_artifact"))
    return outputs


def stage_linux(table: dict, root: Path, workspace: Path, env: dict, runner=run_bash) -> dict:
    if env.get("RUNNER_OS") != "Linux":
        return {}
    names = Names(
        table, "linux",
        ver=env_value(env, "VER"),
        arch=env_value(env, "ARCH", required=False),
        ubuntu=env_value(env, "UBUNTU"),
        ubuntu_str=env_value(env, "UBUNTU_STR"),
    )
    old, new = workspace / names.old("appimage"), workspace / names.new("appimage")
    if old.is_file():
        old.replace(new)
    if not new.is_file():
        raise PackageError(f"no AppImage {old.name} in {old.parent}")
    remove(workspace / names.new("validator"))
    return {"appimage_name": names.new("artifact"), "appimage_path": str(new), "delete": [names.old("artifact")]}


def stage_flatpak(table: dict, root: Path, workspace: Path, env: dict, runner=run_bash) -> dict:
    if env.get("RUNNER_OS") != "Linux":
        return {}
    arch = FLATPAK_ARCH.get(env.get("RUNNER_ARCH", ""))
    if arch is None:
        raise PackageError(f"no Flatpak arch for RUNNER_ARCH={env.get('RUNNER_ARCH', '')!r}")
    names = Names(table, "flatpak", ver=env_value(env, "VER"), arch=arch)
    old, new = workspace / names.old("bundle"), workspace / names.new("bundle")
    if old.is_file():
        old.replace(new)
    if not new.is_file():
        raise PackageError(f"no Flatpak bundle {old.name} in {workspace}")
    return {"flatpak_name": names.new("artifact"), "flatpak_path": str(new), "delete": [names.old("artifact")]}


RUNNERS = {
    "mac-app": stage_mac_app,
    "mac-upload": stage_mac_upload,
    "windows": stage_windows,
    "linux": stage_linux,
    "flatpak": stage_flatpak,
}


def run_stage(stage: str, root: Path, env: dict, runner=run_bash) -> dict:
    workspace = Path(env.get("GITHUB_WORKSPACE") or root)
    return RUNNERS[stage](load_table(root), root, workspace, env, runner)


def format_outputs(outputs: dict) -> str:
    """GITHUB_OUTPUT lines; `delete` is a multi-line value."""
    lines = []
    for key, value in sorted(outputs.items()):
        if isinstance(value, list):
            lines += [f"{key}<<COSMYX_EOF", *value, "COSMYX_EOF"]
        else:
            lines.append(f"{key}={value}")
    return "".join(line + "\n" for line in lines)


def main(argv: list[str] | None = None, env: dict | None = None, runner=run_bash) -> int:
    parser = argparse.ArgumentParser(description="Give the CI packages and artifacts their CosmoSlice names.")
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this checkout)")
    parser.add_argument("--output", type=Path, help="outputs file (default: $GITHUB_OUTPUT, else stdout)")
    args = parser.parse_args(argv)
    env = dict(os.environ) if env is None else env
    try:
        outputs = run_stage(args.stage, args.root.resolve(), env, runner)
    except (PackageError, OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        print(f"::error::package names ({args.stage}): {error}")
        return 1
    text = format_outputs(outputs)
    target = args.output or (Path(env["GITHUB_OUTPUT"]) if env.get("GITHUB_OUTPUT") else None)
    if target is None:
        sys.stdout.write(text)
    else:
        with open(target, "a", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    print(f"package names ({args.stage}): {', '.join(sorted(outputs)) or 'nothing to do on this leg'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
