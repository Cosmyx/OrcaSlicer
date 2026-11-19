"""Comparison of a pass with the goldens (decision 0168, tolerance.json).

- Linux (pinned Docker image, Mesa llvmpipe): byte-exact, like every golden of
  the shared rules.
- Windows and macOS (native runners, system widgets and WebView): a pixel
  differs when one channel moves by more than `channel_delta`; the image fails
  when more than `max_diff_ratio` of its pixels differ, when one
  `tile` x `tile` tile has more than `max_tile_ratio` of its pixels differing,
  or when its size changed. Recorded exception: decision 0168.
- Text goldens (menu tree, WebView text, surfaces.txt) are byte-exact on every
  OS. environment.json is reported, never compared.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from . import GoldenError
from . import png as png_mod

NOT_COMPARED = {"environment.json"}
GOLDEN_SUFFIXES = (".png", ".txt")


@dataclass(frozen=True)
class Tolerance:
    exact: bool = True
    channel_delta: int = 0
    max_diff_ratio: float = 0.0
    tile: int = 16
    max_tile_ratio: float = 0.0
    webview_mask: bool = False


def load_tolerance(path: Path, os_name: str) -> Tolerance:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1 or os_name not in data:
        raise GoldenError(f"{path}: no version 1 entry for {os_name}")
    entry = data[os_name]
    mode = entry.get("mode")
    if mode not in ("exact", "tolerance"):
        raise GoldenError(f"{path}: {os_name}.mode must be exact or tolerance")
    return Tolerance(exact=mode == "exact", channel_delta=int(entry.get("channel_delta", 0)),
                     max_diff_ratio=float(entry.get("max_diff_ratio", 0.0)), tile=int(entry.get("tile", 16)),
                     max_tile_ratio=float(entry.get("max_tile_ratio", 0.0)),
                     webview_mask=bool(entry.get("webview_mask", False)))


def halved(tolerance: Tolerance) -> Tolerance:
    """Stability between two passes of one run: half the comparison tolerance."""
    return replace(tolerance, channel_delta=tolerance.channel_delta // 2, max_diff_ratio=tolerance.max_diff_ratio / 2,
                   max_tile_ratio=tolerance.max_tile_ratio / 2)


@dataclass
class Diff:
    ok: bool
    reason: str = ""
    differing: int = 0
    ratio: float = 0.0
    worst_tile_ratio: float = 0.0


def compare_images(golden: png_mod.Image, actual: png_mod.Image, tolerance: Tolerance) -> Diff:
    if (golden.width, golden.height) != (actual.width, actual.height):
        return Diff(False, f"size {actual.width}x{actual.height}, golden {golden.width}x{golden.height}")
    if golden.rgba == actual.rgba:
        return Diff(True)
    if tolerance.exact:
        return Diff(False, "pixels differ (byte-exact OS)")
    width, height, tile = golden.width, golden.height, max(1, tolerance.tile)
    tiles_x = (width + tile - 1) // tile
    tile_counts: dict[int, int] = {}
    differing = 0
    stride = width * 4
    delta = tolerance.channel_delta
    for y in range(height):
        row_g = golden.rgba[y * stride:(y + 1) * stride]
        row_a = actual.rgba[y * stride:(y + 1) * stride]
        if row_g == row_a:
            continue
        for x in range(width):
            i = x * 4
            if row_g[i:i + 4] == row_a[i:i + 4]:
                continue
            if max(abs(row_g[i + c] - row_a[i + c]) for c in range(4)) > delta:
                differing += 1
                key = (y // tile) * tiles_x + x // tile
                tile_counts[key] = tile_counts.get(key, 0) + 1
    ratio = differing / (width * height)
    worst = 0.0
    for key, count in tile_counts.items():
        tx, ty = key % tiles_x, key // tiles_x
        area = min(tile, width - tx * tile) * min(tile, height - ty * tile)
        worst = max(worst, count / area)
    if ratio > tolerance.max_diff_ratio:
        return Diff(False, f"{differing} pixels differ ({ratio:.4%} > {tolerance.max_diff_ratio:.4%})", differing, ratio, worst)
    if worst > tolerance.max_tile_ratio:
        return Diff(False, f"a {tile}x{tile} tile differs by {worst:.1%} (> {tolerance.max_tile_ratio:.1%})", differing, ratio,
                    worst)
    return Diff(True, "within tolerance" if differing else "", differing, ratio, worst)


def compare_files(golden: Path, actual: Path, tolerance: Tolerance) -> Diff:
    golden_bytes, actual_bytes = golden.read_bytes(), actual.read_bytes()
    if golden_bytes == actual_bytes:
        return Diff(True)
    if golden.suffix != ".png":
        return Diff(False, "text differs")
    return compare_images(png_mod.decode(golden_bytes), png_mod.decode(actual_bytes), tolerance)


@dataclass
class Result:
    name: str
    status: str  # pass, fail, missing (no golden), gone (golden not produced)
    reason: str = ""


def golden_names(directory: Path) -> set[str]:
    if not directory.is_dir():
        return set()
    return {p.name for p in directory.iterdir()
            if p.is_file() and p.suffix in GOLDEN_SUFFIXES and p.name not in NOT_COMPARED}


def compare_dirs(golden_dir: Path, actual_dir: Path, tolerance: Tolerance) -> list[Result]:
    goldens, actuals = golden_names(golden_dir), golden_names(actual_dir)
    results = []
    for name in sorted(goldens | actuals):
        if name not in goldens:
            results.append(Result(name, "missing", "no committed golden"))
        elif name not in actuals:
            results.append(Result(name, "gone", "the pass did not produce it"))
        else:
            diff = compare_files(golden_dir / name, actual_dir / name, tolerance)
            results.append(Result(name, "pass" if diff.ok else "fail", diff.reason))
    return results


def passed(results: list[Result]) -> bool:
    return bool(results) and all(r.status == "pass" for r in results)
