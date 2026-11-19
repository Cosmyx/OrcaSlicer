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
