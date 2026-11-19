"""Tests of the committed logo overlay (T11b): rows, sources, sizes and derived renders.

The fresh-render test needs the pinned resvg image (linux containers in Docker); it skips, with the reason,
on a host where that image cannot run.
"""

from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

COSMYX_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = COSMYX_DIR.parents[1]
if str(COSMYX_DIR) not in sys.path:
    sys.path.insert(0, str(COSMYX_DIR))

from branding import OVERLAY_DIR, file_sha256  # noqa: E402
from branding import manifest as manifest_module  # noqa: E402
from branding.derive import derive, icns, ico, raster  # noqa: E402

PREFIX = OVERLAY_DIR + "/"
# Upstream SVGs whose CosmoSlice replacement is the square master, not the upstream aspect ratio. Both are
# unreferenced upstream (no call site loads them); the reviewer sees this in the review table.
SQUARE_MASTER_EXCEPTIONS = {
    "resources/images/OrcaSlicer_gradient_narrow.svg",
    "resources/images/studio_logo.svg",
}
# Rows with no source yet: the asset must come from the user (never drawn or approximated here).
EXPECTED_MISSING = {
    "resources/images/OrcaSlicer_horizontal_dark.svg",
    "resources/images/OrcaSlicer_horizontal_light.svg",
    "resources/web/image/logo2.png",
}


def logo_rows() -> list:
    return manifest_module.load(REPO_ROOT).groups["logos"]


def derived_outputs() -> dict:
    return {entry.output[len(PREFIX) :]: entry for entry in derive.load_manifest(derive.MANIFEST, REPO_ROOT)}


def tracked_upstream_hashes() -> set:
    """sha256 of every tracked file outside the Cosmyx paths, as git stores it (raw bytes)."""
    listing = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-s", "--", "resources", "scripts/msix"],
        capture_output=True, text=True, check=True,
    ).stdout  # fmt: skip
    hashes = set()
    for line in listing.splitlines():
        path = line.split("\t", 1)[1]
        if re.search(r"\.(png|ico|icns|svg|gif)$", path):
            hashes.add(file_sha256(REPO_ROOT / path))
    return hashes


def svg_ratio(data: bytes) -> float:
    size = manifest_module._svg_size(data)
    width, height = (float(part) for part in size.split("x"))
    return width / height


class LogoRowsTest(unittest.TestCase):
    def test_every_overlay_row_has_a_source_and_waits_for_review(self) -> None:
        for row in logo_rows():
            with self.subTest(path=row["path"]):
                if row["path"] in EXPECTED_MISSING:
                    self.assertEqual(row["status"], "missing")
                    self.assertFalse(manifest_module.overlay_path(REPO_ROOT, row["path"]).exists())
                    continue
                self.assertIn(row["status"], ("to-validate", "validated"))
                self.assertIn(row["source"], ("cosmoslice", "derived"))
                self.assertTrue(row["source_ref"])
                overlay = manifest_module.overlay_path(REPO_ROOT, row["path"])
                self.assertEqual(file_sha256(overlay), row["override_sha256"])

    def test_derived_rows_match_the_derivation_list(self) -> None:
        outputs = derived_outputs()
        derived_rows = {row["path"] for row in logo_rows() if row["source"] == "derived"}
        self.assertEqual(derived_rows, set(outputs))
        for entry in outputs.values():
            self.assertEqual(entry.source, PREFIX + "resources/images/OrcaSlicer.svg")

    def test_no_overlay_file_is_an_orca_original(self) -> None:
        upstream = tracked_upstream_hashes()
        for row in logo_rows():
            if row["override_sha256"] is None:
                continue
            with self.subTest(path=row["path"]):
                self.assertNotEqual(row["override_sha256"], row["upstream_sha256"])
                self.assertNotIn(row["override_sha256"], upstream)

    def test_sizes_match_the_manifest(self) -> None:
        for row in logo_rows():
            overlay = manifest_module.overlay_path(REPO_ROOT, row["path"])
            if not overlay.is_file():
                continue
            data = overlay.read_bytes()
            with self.subTest(path=row["path"]):
                if row["format"] in ("png", "ico"):
                    self.assertEqual(manifest_module.image_size(overlay), row["size"])
                elif row["format"] == "icns":
                    sizes = sorted({icns.png_size(payload)[0] for _, payload in icns.parse_icns(data)})
                    self.assertEqual(tuple(sizes), icns.REQUIRED_SIZES)
                elif row["path"] not in SQUARE_MASTER_EXCEPTIONS:
                    self.assertAlmostEqual(svg_ratio(data), svg_ratio(_svg_tag(row)), places=2)

    def test_ico_layout_matches_upstream(self) -> None:
        row = next(row for row in logo_rows() if row["path"] == "resources/images/OrcaSlicer.ico")
        data = manifest_module.overlay_path(REPO_ROOT, row["path"]).read_bytes()
        entries = ico.parse_ico(data)
        self.assertEqual(",".join(str(size) for size, _, _ in entries), row["size"])
        self.assertEqual(
            [kind for size, kind, _ in entries], ["png" if size == 256 else "bmp" for size, _, _ in entries]
        )

    def test_grayscale_logo_is_gray(self) -> None:
        path = manifest_module.overlay_path(REPO_ROOT, "resources/images/OrcaSlicer_192px_grayscale.png")
        image = raster.decode(path.read_bytes())
        pixels = image.rgba
        self.assertTrue(all(pixels[i] == pixels[i + 1] == pixels[i + 2] for i in range(0, len(pixels), 4)))


def _svg_tag(row: dict) -> bytes:
    """A minimal SVG with the row's recorded (upstream) size as viewBox, to compare aspect ratios."""
    width, height = row["size"].split("x")
    return f'<svg viewBox="0 0 {width} {height}">'.encode()


class FreshRenderTest(unittest.TestCase):
    def test_derived_outputs_equal_a_fresh_render(self) -> None:
        reason = derive.docker_unavailable() if derive.shutil.which("resvg") is None else None
        if reason:
            self.skipTest(f"pinned resvg image unavailable ({reason}); run `just brand-derive-check` where it is")
        if derive.shutil.which("resvg"):
            stale = derive.check(derive.load_manifest(), REPO_ROOT, derive.resvg_renderer())
            self.assertEqual(stale, [])
            return
        result = derive.run_in_docker("check", capture=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(", 0 stale", result.stdout)


if __name__ == "__main__":
    unittest.main()
