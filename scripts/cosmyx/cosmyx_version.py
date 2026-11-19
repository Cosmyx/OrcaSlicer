"""Compute the Cosmyx display version and the CI build tag (decisions 0060-0063).

The display version is "<SoftFever_VERSION>-<Cosmyx patch>", e.g. 2.6.0-8, or 2.6.0-dev-8 on a development base.
SoftFever_VERSION is read from version.inc and the patch from the C++ header that the app is built with, so the
app and the build names cannot disagree. The build tag appends the short commit hash the app embeds, e.g.
2.6.0-dev-8_aa9dac8.

    cosmyx_version.py version                     -> 2.6.0-dev-8
    cosmyx_version.py build-tag  [--commit SHA]   -> 2.6.0-dev-8_aa9dac8
    cosmyx_version.py github-env [--commit SHA]   -> appends ver=<build tag> to $GITHUB_ENV

The commit follows src/slic3r/GitCommitHash.cmake: the git_commit_hash environment variable when it is set (pull
requests), shortened by git, otherwise `git log -1 --format=%h`.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_INC = Path("version.inc")
VERSION_HEADER = Path("src", "slic3r", "GUI", "Cosmyx", "logic", "CosmyxVersion.hpp")

UPSTREAM = re.compile(r'^\s*set\(\s*SoftFever_VERSION\s+"([^"]*)"\s*\)', re.MULTILINE)
PATCH = re.compile(r"^\s*inline\s+constexpr\s+int\s+patch_version\s*=\s*(\d+)\s*;", re.MULTILINE)
UPSTREAM_FORMAT = re.compile(r"\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?")
COMMIT = re.compile(r"[0-9a-f]{7,40}")
MIN_PATCH = 8


class VersionError(Exception):
    pass


def upstream_version(root: Path = REPO_ROOT) -> str:
    """SoftFever_VERSION from version.inc, as CMake sets it."""
    path = root / VERSION_INC
    match = UPSTREAM.search(path.read_text(encoding="utf-8"))
    if not match:
        raise VersionError(f"{VERSION_INC.as_posix()}: no set(SoftFever_VERSION \"...\") line")
    value = match[1]
    if not UPSTREAM_FORMAT.fullmatch(value):
        raise VersionError(f"{VERSION_INC.as_posix()}: SoftFever_VERSION is {value!r}, expected <x>.<y>.<z>[-<tag>]")
    return value


def patch_version(root: Path = REPO_ROOT) -> int:
    """The Cosmyx patch number from the C++ header."""
    path = root / VERSION_HEADER
    matches = PATCH.findall(path.read_text(encoding="utf-8"))
    if len(matches) != 1:
        raise VersionError(f"{VERSION_HEADER.as_posix()}: expected one `inline constexpr int patch_version = N;` line")
    value = int(matches[0])
    if value < MIN_PATCH:
        raise VersionError(f"{VERSION_HEADER.as_posix()}: patch_version is {value}, Cosmyx patches start at {MIN_PATCH}")
    return value


def compose_display_version(upstream: str, patch: int) -> str:
    """Same rule as Cosmyx::compose_display_version() in C++: the upstream suffix is kept."""
    return f"{upstream}-{patch}"


def display_version(root: Path = REPO_ROOT) -> str:
    return compose_display_version(upstream_version(root), patch_version(root))


def build_tag(version: str, commit: str) -> str:
    if not COMMIT.fullmatch(commit):
        raise VersionError(f"commit {commit!r} is not a lower-case hex hash of 7 to 40 characters")
    return f"{version}_{commit}"


Runner = Callable[[list[str]], str]


def git_runner(cwd: Path) -> Runner:
    def run(args: list[str]) -> str:
        return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout

    return run


def head_commit(run: Runner, env: Mapping[str, str]) -> str:
    """The short hash GitCommitHash.cmake embeds as GIT_COMMIT_HASH."""
    requested = env.get("git_commit_hash", "").strip()
    if requested:
        try:
            return run(["git", "rev-parse", "--short", requested]).strip()
        except (OSError, subprocess.CalledProcessError):
            # Not in a shallow checkout: the same cut CMake makes without git.
            return requested[:7].lower()
    return run(["git", "log", "-1", "--format=%h"]).strip()


def main(argv: list[str] | None = None, env: Mapping[str, str] | None = None, run: Runner | None = None) -> int:
    env = os.environ if env is None else env
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root (default: this checkout)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="print the display version")
    for name in ("build-tag", "github-env"):
        cmd = sub.add_parser(name, help="print the build tag" if name == "build-tag" else "write ver= to $GITHUB_ENV")
        cmd.add_argument("--commit", help="short commit hash (default: the one the build embeds)")
    args = parser.parse_args(argv)
    try:
        version = display_version(args.root)
        if args.command == "version":
            print(version)
            return 0
        commit = args.commit or head_commit(run or git_runner(args.root), env)
        tag = build_tag(version, commit)
        if args.command == "github-env":
            target = env.get("GITHUB_ENV", "")
            if not target:
                raise VersionError("GITHUB_ENV is not set; github-env only runs inside GitHub Actions")
            with open(target, "a", encoding="utf-8", newline="\n") as out:
                out.write(f"ver={tag}\n")
        print(tag)
    except (VersionError, OSError, subprocess.CalledProcessError) as error:
        print(f"cosmyx_version: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
