"""Tests of the branding derivation tool (scripts/cosmyx/branding/derive) with a fake renderer.

The real renders (pinned resvg) are checked by test_branding_logos.py.
"""

from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

COSMYX_DIR = Path(__file__).resolve().parents[1]
if str(COSMYX_DIR) not in sys.path:
    sys.path.insert(0, str(COSMYX_DIR))

from branding.derive import derive, icns, ico, raster  # noqa: E402


def solid_png(size: int, salt: int = 0) -> bytes:
    """A real RGBA PNG: a gradient keyed on `salt`, with a fully transparent first column."""
    pixels = bytearray()
    for y in range(size):
        for x in range(size):
            pixels += bytes(((x * 7 + salt) & 0xFF, (y * 5 + salt) & 0xFF, (x + y + salt) & 0xFF, 0 if x == 0 else 200))
    return raster.encode(raster.Image(size, size, bytes(pixels)))


def fake_renderer(source: Path, size: int) -> bytes:
    return solid_png(size, len(source.read_bytes()))


class TreeCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "logo.svg").write_text("<svg/>", encoding="utf-8")
        (self.root / "out").mkdir()

    def manifest(self, body: str) -> Path:
        path = self.root / "derived-assets.toml"
        path.write_text(body, encoding="utf-8")
        return path


class RasterTest(unittest.TestCase):
    def test_round_trip_keeps_pixels(self) -> None:
        data = solid_png(9, 3)
        image = raster.decode(data)
        self.assertEqual((image.width, image.height), (9, 9))
        self.assertEqual(raster.encode(image), data)

    def test_decodes_every_filter_and_rgb(self) -> None:
        import zlib

        width, height = 3, 5
        rows = [bytes(range(i * 9, i * 9 + 9)) for i in range(height)]
        # Filter each row with its own type (0..4) the way a PNG encoder would.
        raw = b""
        previous = bytes(9)
        for kind, row in enumerate(rows):
            out = bytearray()
            for i in range(9):
                left = row[i - 3] if i >= 3 else 0
                up = previous[i]
                corner = previous[i - 3] if i >= 3 else 0
                predictor = [0, left, up, (left + up) >> 1, raster._paeth(left, up, corner)][kind]
                out.append((row[i] - predictor) & 0xFF)
            raw += bytes([kind]) + bytes(out)
            previous = row
        header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        data = (
            raster.PNG_SIGNATURE
            + raster._chunk(b"IHDR", header)
            + raster._chunk(b"IDAT", zlib.compress(raw))
            + raster._chunk(b"IEND", b"")
        )
        image = raster.decode(data)
        expected = b"".join(row[i : i + 3] + b"\xff" for row in rows for i in range(0, 9, 3))
        self.assertEqual(image.rgba, expected)

    def test_rejects_unsupported_png(self) -> None:
        header = struct.pack(">IIBBBBB", 1, 1, 16, 6, 0, 0, 0)
        data = raster.PNG_SIGNATURE + raster._chunk(b"IHDR", header) + raster._chunk(b"IEND", b"")
        with self.assertRaisesRegex(ValueError, "unsupported"):
            raster.decode(data)
        with self.assertRaisesRegex(ValueError, "not a PNG"):
            raster.decode(b"GIF89a")

    def test_grayscale_uses_bt601_luma_and_keeps_alpha(self) -> None:
        image = raster.Image(2, 1, bytes((128, 0, 255, 10, 255, 255, 255, 0)))
        gray = raster.grayscale(image)
        value = (299 * 128 + 587 * 0 + 114 * 255 + 500) // 1000
        self.assertEqual(gray.rgba, bytes((value, value, value, 10, 255, 255, 255, 0)))

    def test_grayscale_output_has_no_colour(self) -> None:
        gray = raster.decode(raster.encode(raster.grayscale(raster.decode(solid_png(16, 9)))))
        for i in range(0, len(gray.rgba), 4):
            self.assertEqual(gray.rgba[i], gray.rgba[i + 1])
            self.assertEqual(gray.rgba[i], gray.rgba[i + 2])


class IcoTest(unittest.TestCase):
    SIZES = (16, 32, 48, 64, 128, 256)

    def test_layout_follows_upstream(self) -> None:
        data = ico.write_ico({size: solid_png(size) for size in self.SIZES})
        entries = ico.parse_ico(data)
        self.assertEqual([size for size, _, _ in entries], list(self.SIZES))
        self.assertEqual([kind for _, kind, _ in entries], ["bmp"] * 5 + ["png"])
        self.assertEqual(entries[-1][2], solid_png(256))

    def test_bitmap_entry_is_bottom_up_bgra_with_mask(self) -> None:
        data = ico.write_ico({2: solid_png(2)})
        _, kind, payload = ico.parse_ico(data)[0]
        self.assertEqual(kind, "bmp")
        header = ico.DIB_HEADER.unpack_from(payload, 0)
        self.assertEqual(header[1:5], (2, 4, 1, 32))
        image = raster.decode(solid_png(2))
        top_left_bgra = bytes((image.rgba[2], image.rgba[1], image.rgba[0], image.rgba[3]))
        # Bottom-up: the first stored row is the image's last row; the top row comes second.
        self.assertEqual(payload[40 + 8 : 40 + 12], top_left_bgra)
        mask = payload[40 + 16 :]
        self.assertEqual(len(mask), 8)
        # Column 0 is transparent: its mask bit is set on both rows.
        self.assertEqual(mask[0], 0x80)
        self.assertEqual(mask[4], 0x80)

    def test_deterministic(self) -> None:
        pngs = {size: solid_png(size) for size in (16, 256)}
        self.assertEqual(ico.write_ico(pngs), ico.write_ico(dict(reversed(list(pngs.items())))))

    def test_rejects_bad_payloads(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least one"):
            ico.write_ico({})
        with self.assertRaisesRegex(ValueError, "1 to 256"):
            ico.write_ico({512: solid_png(512)})
        with self.assertRaisesRegex(ValueError, "16x16"):
            ico.write_ico({16: solid_png(8)})

    def test_parser_rejects_malformed_files(self) -> None:
        for data in (b"", b"\x00\x00\x02\x00\x01\x00", b"\x00\x00\x01\x00\x01\x00", b"\x00\x00\x01\x00\x00\x00"):
            with self.subTest(data=data), self.assertRaises(ValueError):
                ico.parse_ico(data)


class IcnsTest(unittest.TestCase):
    def pngs(self) -> dict:
        return {
            size: solid_png(size) if size <= 64 else raster.encode(raster.Image(size, size, bytes(4 * size * size)))
            for size in icns.REQUIRED_SIZES
        }

    def test_entry_table_is_fixed(self) -> None:
        self.assertEqual(icns.REQUIRED_SIZES, (16, 32, 64, 128, 256, 512, 1024))
        self.assertNotIn("icp6", [kind for kind, _ in icns.ENTRIES])

    def test_round_trip(self) -> None:
        pngs = self.pngs()
        chunks = icns.parse_icns(icns.write_icns(pngs))
        self.assertEqual([kind for kind, _ in chunks], [kind for kind, _ in icns.ENTRIES])
        for (kind, size), (_, payload) in zip(icns.ENTRIES, chunks):
            self.assertEqual(payload, pngs[size], kind)

    def test_rejects_missing_or_wrong_sizes(self) -> None:
        pngs = self.pngs()
        del pngs[16]
        with self.assertRaisesRegex(ValueError, "missing"):
            icns.write_icns(pngs)
        pngs = self.pngs()
        pngs[16] = solid_png(8)
        with self.assertRaisesRegex(ValueError, "16 px payload is 8x8"):
            icns.write_icns(pngs)

    def test_parser_rejects_malformed_files(self) -> None:
        for data in (b"", b"icnx\x00\x00\x00\x08", b"icns\x00\x00\x00\x09\x00", b"icns\x00\x00\x00\x0cic07"):
            with self.subTest(data=data):
                self.assertFalse(icns.is_valid_icns(data))


class ManifestTest(TreeCase):
    def test_reads_every_format(self) -> None:
        path = self.manifest(
            '[[derived]]\nsource = "logo.svg"\noutput = "out/a.png"\nformat = "png"\nsize = 192\ngrayscale = true\n'
            '[[derived]]\nsource = "logo.svg"\noutput = "out/a.ico"\nformat = "ico"\nsize = [256, 16]\n'
            '[[derived]]\nsource = "logo.svg"\noutput = "out/a.icns"\nformat = "icns"\n'
        )
        self.assertEqual(
            derive.load_manifest(path, self.root),
            [
                derive.Entry("logo.svg", "out/a.png", "png", 192, True),
                derive.Entry("logo.svg", "out/a.ico", "ico", (16, 256)),
                derive.Entry("logo.svg", "out/a.icns", "icns", None),
            ],
        )

    def test_accepts_an_empty_manifest(self) -> None:
        self.assertEqual(derive.load_manifest(self.manifest("# nothing\n"), self.root), [])

    def test_rejects_invalid_entries(self) -> None:
        cases = {
            'source = "missing.svg"\noutput = "o.png"\nformat = "png"\nsize = 1': "does not exist",
            'source = "logo.svg"\noutput = "o.png"\nformat = "png"': "positive integer size",
            'source = "logo.svg"\noutput = "o.png"\nformat = "png"\nsize = true': "positive integer size",
            'source = "logo.svg"\noutput = "o.icns"\nformat = "icns"\nsize = 2': "takes no size",
            'source = "logo.svg"\noutput = "o.ico"\nformat = "ico"\nsize = [512]': "from 1 to 256",
            'source = "logo.svg"\noutput = "o.ico"\nformat = "ico"\nsize = [16, 16]': "twice",
            'source = "logo.svg"\noutput = "o.ico"\nformat = "ico"\nsize = 16': "list of sizes",
            'source = "logo.svg"\noutput = "o.ico"\nformat = "ico"\nsize = [16]\ngrayscale = true': "grayscale only",
            'source = "logo.svg"\noutput = "o.png"\nformat = "png"\nsize = 1\ngrayscale = "yes"': "true or false",
            'source = "logo.svg"\noutput = "o.gif"\nformat = "gif"': "format",
            'source = "logo.svg"\noutput = "../o.png"\nformat = "png"\nsize = 1': "without '..'",
            'source = "logo.svg"\noutput = "/o.png"\nformat = "png"\nsize = 1': "without '..'",
            'source = "logo.svg"\noutput = "C:/o.png"\nformat = "png"\nsize = 1': "without '..'",
            'source = "logo.svg"\noutput = "out\\\\o.png"\nformat = "png"\nsize = 1': "POSIX",
            'source = "logo.svg"\noutput = "logo.svg"\nformat = "png"\nsize = 1': "its own source",
            'source = "logo.svg"\noutput = "o.png"\nformat = "png"\nsize = 1\ncolour = 1': "unknown keys",
        }
        for body, message in cases.items():
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, message):
                derive.load_manifest(self.manifest("[[derived]]\n" + body + "\n"), self.root)

    def test_rejects_duplicates_and_chains(self) -> None:
        entry = '[[derived]]\nsource = "logo.svg"\noutput = "out/a.png"\nformat = "png"\nsize = 1\n'
        with self.assertRaisesRegex(ValueError, "duplicate"):
            derive.load_manifest(self.manifest(entry * 2), self.root)
        (self.root / "out" / "a.png").write_bytes(b"x")
        chained = entry + '[[derived]]\nsource = "out/a.png"\noutput = "out/b.png"\nformat = "png"\nsize = 1\n'
        with self.assertRaisesRegex(ValueError, "used as sources"):
            derive.load_manifest(self.manifest(chained), self.root)

    def test_rejects_a_derived_key_that_is_not_an_array(self) -> None:
        with self.assertRaisesRegex(ValueError, "array of tables"):
            derive.load_manifest(self.manifest('derived = "x"\n'), self.root)
        with self.assertRaisesRegex(ValueError, "must be a table"):
            derive.load_manifest(self.manifest("derived = [1]\n"), self.root)


class PipelineTest(TreeCase):
    def entries(self) -> list:
        return [
            derive.Entry("logo.svg", "out/logo.png", "png", 154),
            derive.Entry("logo.svg", "out/gray.png", "png", 8, True),
            derive.Entry("logo.svg", "out/app.ico", "ico", (16, 256)),
            derive.Entry("logo.svg", "out/app.icns", "icns", None),
        ]

    def test_render_entries(self) -> None:
        entries = self.entries()
        self.assertEqual(
            derive.render_entry(entries[0], self.root, fake_renderer), fake_renderer(self.root / "logo.svg", 154)
        )
        gray = raster.decode(derive.render_entry(entries[1], self.root, fake_renderer))
        self.assertEqual(gray, raster.grayscale(raster.decode(fake_renderer(self.root / "logo.svg", 8))))
        sizes = [size for size, _, _ in ico.parse_ico(derive.render_entry(entries[2], self.root, fake_renderer))]
        self.assertEqual(sizes, [16, 256])
        payloads = dict(icns.parse_icns(derive.render_entry(entries[3], self.root, fake_renderer)))
        self.assertEqual(icns.png_size(payloads["ic10"]), (1024, 1024))

    def test_render_entry_rejects_missing_sizes(self) -> None:
        with self.assertRaisesRegex(ValueError, "has no size"):
            derive.render_entry(derive.Entry("logo.svg", "o.png", "png", None), self.root, fake_renderer)
        with self.assertRaisesRegex(ValueError, "has no sizes"):
            derive.render_entry(derive.Entry("logo.svg", "o.ico", "ico", None), self.root, fake_renderer)

    def test_write_creates_then_leaves_unchanged_files_alone(self) -> None:
        entries = self.entries()[:1] + [derive.Entry("logo.svg", "new dir/é.png", "png", 4)]
        self.assertEqual(derive.write(entries, self.root, fake_renderer), ["out/logo.png", "new dir/é.png"])
        logo = self.root / "out" / "logo.png"
        os.utime(logo, (1, 1))
        self.assertEqual(derive.write(entries, self.root, fake_renderer), [])
        self.assertEqual(logo.stat().st_mtime, 1)

    def test_check_lists_stale_and_missing_outputs(self) -> None:
        entries = self.entries()
        (self.root / "out" / "logo.png").write_bytes(b"old orca bytes")
        self.assertEqual(derive.check(entries, self.root, fake_renderer), [e.output for e in entries])
        derive.write(entries, self.root, fake_renderer)
        self.assertEqual(derive.check(entries, self.root, fake_renderer), [])

    def test_stable_reports_differing_runs(self) -> None:
        entries = self.entries()[:1]
        self.assertEqual(derive.stable(entries, self.root, fake_renderer), [])
        calls = iter(range(10_000))
        flaky = lambda source, size: solid_png(size, next(calls))  # noqa: E731
        self.assertEqual(derive.stable(entries, self.root, flaky), ["out/logo.png"])


class ResvgTest(unittest.TestCase):
    def test_missing_resvg_fails_with_a_hint(self) -> None:
        with (
            mock.patch.object(derive.shutil, "which", return_value=None),
            self.assertRaisesRegex(derive.ResvgMissingError, "just brand-derive"),
        ):
            derive.find_resvg()

    def test_resvg_failure_reports_stderr_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "broken.svg"
            source.write_text("<svg", encoding="utf-8")
            # Stand-in for resvg: a command that writes to stderr and exits non-zero (extra arguments ignored).
            failing = [sys.executable, "-c", "import sys; sys.stderr.write('resvg: unexpected end'); sys.exit(3)"]
            with self.assertRaises(derive.RenderError) as caught:
                derive.resvg_renderer(failing)(source, 16)
        message = str(caught.exception)
        self.assertIn("resvg: unexpected end", message)
        self.assertIn(str(source), message)
        self.assertIn("exit status 3", message)
        self.assertIsInstance(caught.exception.__cause__, subprocess.CalledProcessError)

    def test_main_without_resvg_exits_2(self) -> None:
        with mock.patch.object(derive.shutil, "which", return_value=None), mock.patch("sys.stderr"):
            self.assertEqual(derive.main(["check"]), 2)


class DockerTest(unittest.TestCase):
    def test_image_tag_follows_the_dockerfile(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            dockerfile = Path(tmp) / "Dockerfile"
            dockerfile.write_bytes(b"FROM scratch\n")
            first = derive.image_tag(dockerfile)
            dockerfile.write_bytes(b"FROM scratch\r\n")
            self.assertEqual(derive.image_tag(dockerfile), first)
            dockerfile.write_bytes(b"FROM busybox\n")
            self.assertNotEqual(derive.image_tag(dockerfile), first)
        self.assertTrue(first.startswith("cosmyx-resvg:"))

    def test_pinned_image(self) -> None:
        text = derive.DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("cargo install resvg --version 0.48.1 --locked", text)
        for line in text.splitlines():
            if line.startswith("FROM "):
                self.assertIn("@sha256:", line)
        self.assertNotIn("COPY ", text.replace("COPY --from=resvg", ""))

    def test_docker_command_mounts_the_tree_and_runs_the_script(self) -> None:
        command = derive.docker_command("cosmyx-resvg:x", "check")
        self.assertEqual(command[:6], ["docker", "run", "--rm", "--platform", "linux/amd64", "--mount"])
        self.assertIn(f"type=bind,source={derive.REPO_ROOT},target=/repo", command)
        self.assertEqual(command[-3:], ["python", "/repo/scripts/cosmyx/branding/derive/derive.py", "check"])

    def test_docker_unavailable_reasons(self) -> None:
        with mock.patch.object(derive.shutil, "which", return_value=None):
            self.assertEqual(derive.docker_unavailable(), "docker is not installed")
        done = subprocess.CompletedProcess([], 0, stdout="windows x86_64\n")
        with (
            mock.patch.object(derive.shutil, "which", return_value="docker"),
            mock.patch.object(derive.subprocess, "run", return_value=done),
        ):
            self.assertIn("windows containers", derive.docker_unavailable())
        failed = subprocess.CompletedProcess([], 1, stdout="")
        with (
            mock.patch.object(derive.shutil, "which", return_value="docker"),
            mock.patch.object(derive.subprocess, "run", return_value=failed),
        ):
            self.assertIn("not reachable", derive.docker_unavailable())

    def docker_runs(self, *results: subprocess.CompletedProcess) -> tuple[str | None, mock.MagicMock]:
        with (
            mock.patch.object(derive.shutil, "which", return_value="docker"),
            mock.patch.object(derive.subprocess, "run", side_effect=list(results)) as run,
        ):
            return derive.docker_unavailable(), run

    def test_native_amd64_daemon_needs_no_probe(self) -> None:
        reason, run = self.docker_runs(subprocess.CompletedProcess([], 0, stdout="linux x86_64\n"))
        self.assertIsNone(reason)
        self.assertEqual(run.call_count, 1)

    def test_arm64_daemon_without_emulation_is_unavailable(self) -> None:
        # An arm64 runner without binfmt fails the first amd64 binary with this error.
        reason, run = self.docker_runs(
            subprocess.CompletedProcess([], 0, stdout="linux aarch64\n"),
            subprocess.CompletedProcess([], 1, stdout="", stderr="exec /usr/bin/true: exec format error\n"),
        )
        self.assertIn("cannot run linux/amd64 containers", reason)
        self.assertIn("exec format error", reason)
        probe = run.call_args_list[1].args[0]
        self.assertEqual(probe[:5], ["docker", "run", "--rm", "--platform", "linux/amd64"])
        self.assertEqual(probe[-2:], [derive.probe_image(), "true"])

    def test_arm64_daemon_with_emulation_is_available(self) -> None:
        reason, run = self.docker_runs(
            subprocess.CompletedProcess([], 0, stdout="linux aarch64\n"),
            subprocess.CompletedProcess([], 0, stdout="", stderr=""),
        )
        self.assertIsNone(reason)
        self.assertEqual(run.call_count, 2)

    def test_probe_image_is_the_pinned_final_stage(self) -> None:
        image = derive.probe_image()
        self.assertIn("@sha256:", image)
        self.assertIn(f"FROM {image} AS final", derive.DOCKERFILE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "Dockerfile"
            empty.write_text("# nothing\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                derive.probe_image(empty)


if __name__ == "__main__":
    unittest.main()
