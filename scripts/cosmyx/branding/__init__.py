"""Cosmyx branding engine (T11).

The OrcaSlicer tree stays untouched in git: the Cosmyx branding (vendored
images, colours, product name) is applied to the checked-out tree at build
time from the tables under `cosmyx-src/branding/`, and undone with `revert`.

Modules:

- `manifest`: the image tables (`manifest/<group>.json`), discovery and sync.
- `overlay`: the vendored files (`overlay/<repo-relative path>`).
- `textpatch`: exact, counted, all-or-nothing text replacements.
- `guards`: the checks G1-G8 and the status policy, run before and after apply.
- `apply`: the apply / revert pipeline and its stages.
- `render`: the review tables under `wiki/cosmyx/branding-assets/`.
- `cli`: the command line (`check`, `apply`, `revert`, `sync`, `refresh`,
  `validate`, `render`).

This file holds what every module shares: paths, errors, findings, hashing,
canonical JSON and the hex colour rule. Standard library only, Python 3.9+.
"""

from __future__ import annotations

import colorsys
import fnmatch
import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from collections.abc import Iterable

# Repository-relative locations, always written with forward slashes.
BRAND_DIR = "cosmyx-src/branding"
MANIFEST_DIR = f"{BRAND_DIR}/manifest"
OVERLAY_DIR = f"{BRAND_DIR}/overlay"
COLOURS_FILE = f"{BRAND_DIR}/colours.json"
PRODUCT_NAME_DIR = f"{BRAND_DIR}/product-name"
TABLES_DIR = "wiki/cosmyx/branding-assets"
STATE_DIR = "build/cosmyx/branding-state"
REPORT_FILE = "build/cosmyx/branding-report.json"

GROUPS = ("logos", "icons-a-m", "icons-n-z", "web")

# Files tracked by the Cosmyx fork itself, where Cosmyx colours and names may
# appear. Everything else is upstream-owned and must stay Orca-branded in git
# (guard G7). Patterns use fnmatch on the repository-relative POSIX path.
COSMYX_PATHS = (
    "cosmyx-src/*",
    "scripts/cosmyx/*",
    "wiki/*",
    "localization/cosmyx/*",
    "src/*/Cosmyx/*",
    "tests/cosmyx/*",
    "resources/cosmyx/*",
    ".github/actions/cosmyx-*",
    ".github/cosmyx/*",
    ".github/workflows/cosmyx-*",
    "*cosmyx*",
    "CHANGELOG.md",
    "justfile",
)

# The teal family the Orca brand colours belong to, used until colours.json
# (T11c) provides its own `family` and `ignore`.
DEFAULT_FAMILY = {"hue": [160, 190], "min_saturation": 0.25, "min_lightness": 0.15}
DEFAULT_IGNORE = ("#00AE42", "#1F8EEA")

TEXT_FORMATS = frozenset({"svg"})


class BrandingError(Exception):
    """A table or a tree is not in the state the engine needs."""


@dataclass(frozen=True)
class Finding:
    """One guard result. `level` is `error` or `warning`."""

    guard: str
    level: str
    path: str
    message: str

    def as_dict(self) -> dict:
        return {"guard": self.guard, "level": self.level, "path": self.path, "message": self.message}

    def __str__(self) -> str:
        where = f" {self.path}:" if self.path else ""
        return f"{self.level}: {self.guard}{where} {self.message}"


def errors(findings: Iterable[Finding]) -> list[Finding]:
    return [finding for finding in findings if finding.level == "error"]


# ---------------------------------------------------------------- paths


def check_relative(path: str) -> str:
    """Return `path` if it is a clean repository-relative POSIX path, else raise.

    Rejected: empty, absolute (`/x`, `C:/x`, `C:x`), backslashes, `.` or `..`
    parts, empty parts and trailing slashes.
    """
    if not isinstance(path, str) or not path:
        raise BrandingError(f"path must be a non-empty string: {path!r}")
    if "\\" in path:
        raise BrandingError(f"path must use forward slashes: {path!r}")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path):
        raise BrandingError(f"path must be relative to the repository root: {path!r}")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise BrandingError(f"path must not contain empty, '.' or '..' parts: {path!r}")
    return path


def repo_path(root: Path, relative: str) -> Path:
    """The on-disk path of a checked repository-relative path."""
    return root.joinpath(*check_relative(relative).split("/"))


def tree_path(root: Path, relative: str) -> Path:
    """The on-disk path of `relative`, checked to be a real file of the tree
    under that exact spelling, for a file the engine writes into.

    Refused: a path that resolves outside `root` (a symlink escaping the
    tree), and a path whose on-disk name differs only by case (`src/file.txt`
    for `src/File.txt`): a case-insensitive macOS or Windows disk would open
    it while Linux would not, so every OS refuses it. Missing files are left
    to the caller.
    """
    path = repo_path(root, relative)
    base = root.resolve()
    try:
        path.resolve().relative_to(base)
    except ValueError:
        raise BrandingError(f"{relative}: resolves outside the repository (symlink?)") from None
    current = root
    for part in relative.split("/"):
        try:
            names = os.listdir(current)
        except OSError:
            break
        if part not in names:
            folded = [name for name in names if name.casefold() == part.casefold()]
            if folded:
                raise BrandingError(f"{relative}: the file on disk is spelled {folded[0]!r}, not {part!r}")
            break
        current = current / part
    return path


def relative_posix(root: Path, path: Path) -> str:
    return PurePosixPath(*path.relative_to(root).parts).as_posix()


def is_cosmyx_path(relative: str) -> bool:
    return any(fnmatch.fnmatchcase(relative, pattern) for pattern in COSMYX_PATHS)


# ---------------------------------------------------------------- hashing


def file_format(path: str) -> str:
    return PurePosixPath(path).suffix.lower().lstrip(".")


def content_sha256(data: bytes, fmt: str) -> str:
    """SHA-256 of a file's content: text formats are hashed over LF bytes."""
    if fmt in TEXT_FORMATS:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path, fmt: str | None = None) -> str:
    return content_sha256(path.read_bytes(), fmt if fmt is not None else file_format(path.name))


# ---------------------------------------------------------------- JSON


def dump_json(data) -> str:
    """Canonical JSON: two-space indent, UTF-8, LF, trailing newline."""
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def load_json(path: Path):
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise BrandingError(f"cannot read {path}: {error}") from error


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 text with LF line endings on every OS."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


# ---------------------------------------------------------------- line endings
#
# A Windows checkout (core.autocrlf, the runners' default) has CRLF text files
# while the repository stores LF. Every text read and match works on LF text;
# every write puts back the file's own dominant line ending, never a mix; every
# comparison with expected content is made on LF.


def line_ending(data: bytes) -> bytes:
    """The dominant line ending of `data`: CRLF when most lines end with it."""
    crlf = data.count(b"\r\n")
    return b"\r\n" if crlf > data.count(b"\n") - crlf else b"\n"


def to_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def decode_text(data: bytes, errors: str = "strict") -> tuple[str, str]:
    """(LF text, line ending) of a file's bytes."""
    return to_lf(data).decode("utf-8", errors), line_ending(data).decode("ascii")


def read_lf(path: Path, errors: str = "strict") -> str:
    """A text file's content with LF line endings, whatever is on disk."""
    return to_lf(path.read_bytes()).decode("utf-8", errors)


def encode_text(text: str, eol: str, errors: str = "strict") -> bytes:
    """LF `text` encoded with `eol` throughout (no mixed line endings)."""
    data = text.replace("\r\n", "\n").encode("utf-8", errors)
    return data if eol == "\n" else data.replace(b"\n", eol.encode("ascii"))


def same_text(path: Path, expected: str) -> bool:
    """True when the file holds `expected`, line endings aside."""
    return to_lf(path.read_bytes()) == expected.replace("\r\n", "\n").encode("utf-8")


# ---------------------------------------------------------------- colours

# The hex rule of the frozen contract: `#RRGGBB` in any case, not followed by
# another hex digit (so `#RRGGBBAA` matches its first six digits and keeps the
# alpha), never inside an `href`, a `url(...)` reference or base64 data.
HEX_RE = re.compile(r"#([0-9A-Fa-f]{6})(?:[0-9A-Fa-f]{2})?(?![0-9A-Fa-f])")
_SKIP_BEFORE_RE = re.compile(r"(?:href\s*=\s*[\"']?|url\(\s*[\"']?)$", re.IGNORECASE)
_BASE64_RE = re.compile(r"base64,[A-Za-z0-9+/=\s]+")


def find_hexes(text: str) -> list[str]:
    """Every brand-relevant `#RRGGBB` colour in `text`, uppercased, in order."""
    text = _BASE64_RE.sub("base64,", text)
    found = []
    for match in HEX_RE.finditer(text):
        before = text[max(0, match.start() - 16) : match.start()]
        if _SKIP_BEFORE_RE.search(before):
            continue
        found.append("#" + match.group(1).upper())
    return found


def in_family(hex_colour: str, family: dict | None = None, ignore: Iterable[str] = DEFAULT_IGNORE) -> bool:
    """True when `#RRGGBB` belongs to the teal family (HSL hue, saturation, lightness)."""
    family = family or DEFAULT_FAMILY
    colour = hex_colour.upper()
    if colour in {item.upper() for item in ignore}:
        return False
    red, green, blue = (int(colour[i : i + 2], 16) / 255.0 for i in (1, 3, 5))
    hue, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    low, high = family["hue"]
    return (
        low <= hue * 360.0 <= high
        and saturation >= family["min_saturation"]
        and lightness >= family["min_lightness"]
    )


# ---------------------------------------------------------------- ref policy


def ref_kind(env: dict | None = None) -> str:
    """Classify the build: `release` (release/* branches and tags) or `development`.

    Pull requests are always `development`, whatever branch they target.
    `COSMYX_BRAND_REF` (a full ref such as `refs/tags/v1`) overrides the
    GitHub variables, for local runs and tests.
    """
    env = os.environ if env is None else env
    override = env.get("COSMYX_BRAND_REF", "")
    if override:
        ref = override
    else:
        if env.get("GITHUB_EVENT_NAME", "").startswith("pull_request"):
            return "development"
        ref = env.get("GITHUB_REF", "")
    if ref.startswith(("refs/tags/", "refs/heads/release/")):
        return "release"
    return "development"


# ---------------------------------------------------------------- mode

MODE_ENV = "COSMYX_BRAND_MODE"
MODES = ("strict", "tolerant")
# Build pull requests of an integration target `cosmyx-ci/<BASE>`, and the
# integration branch of any base other than DEV is `integration/<BASE>`.
CI_BASE_PREFIX = "cosmyx-ci/"
DEV_CI_BASE = f"{CI_BASE_PREFIX}DEV"
INTEGRATION_REF_PREFIX = "refs/heads/integration/"


def local_ref(root: Path) -> str:
    """The full ref (`refs/heads/<branch>`) checked out at `root` when `root` is
    the top of a git worktree, else "" (a detached HEAD, a copy outside git, a
    directory nested in another repository, or no git at all)."""
    try:
        process = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel", "--symbolic-full-name", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except OSError:
        return ""
    lines = process.stdout.decode("utf-8", "replace").splitlines()
    if process.returncode != 0 or len(lines) != 2:
        return ""
    try:
        if Path(lines[0]).resolve() != Path(root).resolve():
            return ""
    except OSError:
        return ""
    return lines[1].strip()


def brand_mode(env: dict | None = None, root: Path | None = None) -> str:
    """`strict` (the default) or `tolerant`.

    The tables are written for DEV. On a tree whose upstream base is not DEV
    (an older upstream tag), a row may name a file or a text that base does not
    have yet: tolerant mode skips such a row with a warning instead of failing.
    On DEV a missing target means upstream removed something, so strict mode
    keeps failing.

    `COSMYX_BRAND_MODE` (`strict` or `tolerant`) decides when set, for local
    runs and for the cosmyx-prepare action, which exports the detected mode.
    Otherwise tolerant is detected for a pull request into `cosmyx-ci/<BASE>`
    with BASE other than DEV, and for a push or dispatch on `integration/*`.
    With `root`, a local checkout of an `integration/*` branch is detected the
    same way, so `just brand-check` and the real-tree tests run in an
    integration worktree brand it as its build will. A release build is always
    strict.
    """
    env = os.environ if env is None else env
    explicit = env.get(MODE_ENV, "").strip()
    if explicit and explicit not in MODES:
        raise BrandingError(f"{MODE_ENV} must be one of {', '.join(MODES)}, not {explicit!r}")
    if explicit:
        mode = explicit
    else:
        base = env.get("GITHUB_BASE_REF", "")
        off_dev = (
            (base.startswith(CI_BASE_PREFIX) and base != DEV_CI_BASE)
            or env.get("GITHUB_REF", "").startswith(INTEGRATION_REF_PREFIX)
            or (root is not None and local_ref(root).startswith(INTEGRATION_REF_PREFIX))
        )
        mode = "tolerant" if off_dev else "strict"
    return "strict" if ref_kind(env) == "release" else mode
