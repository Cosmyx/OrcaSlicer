"""Publish a "Build all" run of the Cosmyx fork to a GitHub draft release (decision 0221).

    python scripts/cosmyx/release_publish.py prepare  --tag TAG --run-id ID [--repo OWNER/NAME]
    python scripts/cosmyx/release_publish.py download --run-id ID [--repo OWNER/NAME] [--dir artifacts]
    python scripts/cosmyx/release_publish.py assemble [--artifacts artifacts] [--upload upload]

The upstream publish_release.yml downloads and assembles `OrcaSlicer_*`
artifacts; a Cosmyx build names them `CosmoSlice_*` (decision 0210), with the
Cosmyx build tag `<display version>_<short hash>` (decision 0062). Its
`# Cosmyx` hook steps run this script instead of the two upstream steps:

- `prepare` (before the upstream draft check): the tag must follow the release
  convention `v<OrcaSlicer base>.<Cosmyx patch>` (v2.5.2.8), every CosmoSlice
  artifact of the run must carry the matching display version (2.5.2-8), so a
  dev, nightly or pre-release build can never be published, and the draft is
  created on the run's commit when it does not exist yet. An existing release
  must be a draft and not a pre-release: the in-app update check never offers
  a pre-release.
- `download`: pulls the CosmoSlice release artifacts of the run (not the MSIX,
  which goes to the Store, nor the profile validator).
- `assemble`: copies the installers, DMG, AppImages, Flatpaks and PDB archive
  to the upload folder, and zips each portable Windows folder.

`gh` must be on PATH with GH_TOKEN set (the workflow does both). Standard
library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Sequence

PRODUCT = "CosmoSlice"
NUMBER = r"(?:0|[1-9][0-9]{0,8})"
TAG = re.compile(rf"v({NUMBER})\.({NUMBER})\.({NUMBER})\.({NUMBER})", re.ASCII)
# <display version>_<short hash>, as cosmyx_version.py build_tag() writes it.
BUILD_TAG = re.compile(r"_([0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.]+)?-[0-9]+)_[0-9a-f]{7,40}(?=_|$)", re.ASCII)
# `gh run download -p` globs. Windows_[0-9]* keeps the MSIX Store artifact out.
DOWNLOAD_PATTERNS = (
    f"{PRODUCT}_Windows_[0-9]*",
    f"{PRODUCT}_Mac_universal_*",
    f"{PRODUCT}_Linux_ubuntu_*",
    f"{PRODUCT}-Linux-flatpak_*",
    "PDB",
)

Runner = Callable[[Sequence[str]], subprocess.CompletedProcess]


class PublishError(Exception):
    pass


def run_gh(args: Sequence[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")


def tag_display_version(tag: str) -> str:
    """v2.5.2.8 -> 2.5.2-8. Anything else is refused."""
    match = TAG.fullmatch(tag)
    if not match:
        raise PublishError(
            f"tag {tag!r} does not follow the Cosmyx release convention v<base>.<patch>, for example v2.5.2.8"
        )
    major, minor, micro, patch = match.groups()
    return f"{major}.{minor}.{micro}-{patch}"


def run_display_versions(artifact_names: Sequence[str]) -> set[str]:
    """The display versions the CosmoSlice artifacts of a run carry."""
    versions = set()
    for name in artifact_names:
        if not name.startswith(PRODUCT):
            continue
        match = BUILD_TAG.search(name)
        if match:
            versions.add(match.group(1))
    return versions


def check_run_matches_tag(tag: str, artifact_names: Sequence[str]) -> str:
    expected = tag_display_version(tag)
    versions = run_display_versions(artifact_names)
    if not versions:
        raise PublishError("the run has no CosmoSlice artifact named after a Cosmyx version")
    if versions != {expected}:
        raise PublishError(
            f"tag {tag} needs a build of version {expected}, the run built {', '.join(sorted(versions))}"
        )
    return expected


def _json(result: subprocess.CompletedProcess, what: str):
    if result.returncode != 0:
        raise PublishError(f"{what} failed: {result.stderr.strip()}")
    return json.loads(result.stdout)


def prepare(tag: str, run_id: str, repo: str, run: Runner = run_gh) -> str:
    display = tag_display_version(tag)
    info = _json(run(["run", "view", run_id, "--repo", repo, "--json", "headSha,workflowName"]), "gh run view")
    listed = run(["api", "--paginate", f"repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100", "--jq", ".artifacts[].name"])
    if listed.returncode != 0:
        raise PublishError(f"listing the run artifacts failed: {listed.stderr.strip()}")
    names = listed.stdout.splitlines()
    check_run_matches_tag(tag, names)
    head_sha = info["headSha"]

    release = run(["release", "view", tag, "--repo", repo, "--json", "isDraft,isPrerelease"])
    if release.returncode == 0:
        state = json.loads(release.stdout)
        if not state.get("isDraft"):
            raise PublishError(f"release {tag} is published, not a draft")
        if state.get("isPrerelease"):
            raise PublishError(f"release {tag} is a pre-release: the update check never offers it, untick it")
        return f"draft release {tag} exists"

    ref = run(["api", f"repos/{repo}/git/ref/tags/{tag}"])
    if ref.returncode == 0:
        target = json.loads(ref.stdout).get("object", {})
        if target.get("type") != "commit" or target.get("sha") != head_sha:
            raise PublishError(f"tag {tag} already exists on another commit than the run's {head_sha}")

    title = f"{PRODUCT} {display}"
    created = run(["release", "create", tag, "--repo", repo, "--draft", "--target", head_sha, "--title", title, "--notes", ""])
    if created.returncode != 0:
        raise PublishError(f"creating draft release {tag} failed: {created.stderr.strip()}")
    return f"created draft release {tag} on {head_sha}"


def download(run_id: str, repo: str, directory: Path, run: Runner = run_gh) -> None:
    args = ["run", "download", run_id, "--repo", repo, "--dir", str(directory)]
    for pattern in DOWNLOAD_PATTERNS:
        args += ["-p", pattern]
    result = run(args)
    if result.returncode != 0:
        raise PublishError(f"gh run download failed: {result.stderr.strip()}")


def _files(root: Path, suffix: str) -> list[Path]:
    # is_file(): some artifact folders are named "*.flatpak".
    return sorted(p for p in root.rglob(f"*{suffix}") if p.is_file())


def _top(path: Path, root: Path) -> str:
    return path.relative_to(root).parts[0]


def assemble(artifacts: Path, upload: Path) -> list[str]:
    """Copy the release files to upload/ and return their names."""
    upload.mkdir(parents=True, exist_ok=True)
    picked: list[Path] = []
    for exe in _files(artifacts, ".exe"):
        top = _top(exe, artifacts)
        if top.startswith(f"{PRODUCT}_Windows_") and not top.endswith("_portable"):
            picked.append(exe)
    picked += [p for p in _files(artifacts, ".dmg") if _top(p, artifacts).startswith(f"{PRODUCT}_Mac_universal_")]
    picked += _files(artifacts, ".AppImage")
    picked += _files(artifacts, ".flatpak")
    picked += sorted(p for p in artifacts.rglob("Debug_PDB_*.7z") if p.is_file())
    for path in picked:
        shutil.copy2(path, upload / path.name)

    portable = sorted(p for p in artifacts.glob(f"{PRODUCT}_Windows_*_portable") if p.is_dir())
    if not portable:
        print("::warning::Windows portable artifact not found.")
    for folder in portable:
        shutil.make_archive(str(upload / folder.name), "zip", root_dir=folder)

    names = sorted(p.name for p in upload.iterdir())
    if not names:
        raise PublishError("no assets assembled: check the run id and that its artifacts have not expired")
    return names


def main(argv: list[str] | None = None, run: Runner = run_gh) -> int:
    parser = argparse.ArgumentParser(description="Publish a Cosmyx Build all run to a draft release.")
    sub = parser.add_subparsers(dest="command", required=True)
    repo_default = os.environ.get("GITHUB_REPOSITORY", "")
    p = sub.add_parser("prepare")
    p.add_argument("--tag", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--repo", default=repo_default)
    d = sub.add_parser("download")
    d.add_argument("--run-id", required=True)
    d.add_argument("--repo", default=repo_default)
    d.add_argument("--dir", type=Path, default=Path("artifacts"))
    a = sub.add_parser("assemble")
    a.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    a.add_argument("--upload", type=Path, default=Path("upload"))
    args = parser.parse_args(argv)
    try:
        if args.command == "prepare":
            print(prepare(args.tag, args.run_id, args.repo, run))
        elif args.command == "download":
            download(args.run_id, args.repo, args.dir, run)
        else:
            print("\n".join(assemble(args.artifacts, args.upload)))
    except PublishError as error:
        print(f"::error::{error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
