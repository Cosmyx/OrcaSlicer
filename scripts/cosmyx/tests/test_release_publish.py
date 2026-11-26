"""Checks of scripts/cosmyx/release_publish.py and of its publish_release.yml
hooks (decision 0221)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "cosmyx"))

import release_publish as rp  # noqa: E402

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish_release.yml"
RELEASE_ARTIFACTS = [
    "CosmoSlice_Windows_2.5.2-8_4a8748a9_x64",
    "CosmoSlice_Windows_2.5.2-8_4a8748a9_x64_portable",
    "CosmoSlice_Windows_MSIX_2.5.2-8_4a8748a9_x64",
    "CosmoSlice_Mac_universal_2.5.2-8_4a8748a9",
    "CosmoSlice_Linux_ubuntu_2404_2.5.2-8_4a8748a9",
    "CosmoSlice_Linux_ubuntu_2404_aarch64_2.5.2-8_4a8748a9",
    "generate_system_cache_Linux_ubuntu_2404_2.5.2-8_4a8748a9",
    "PDB",
    "b8f99642c53ad3ff60817991eecb924b18c5abd6-profile-validator-linux-aarch64",
]


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8")


def upstream_base() -> str | None:
    """The upstream commit this tree is built on, or None when none is found.

    The integration runs the Cosmyx branches on several bases: DEV (a mirror of
    upstream main) or an upstream release tag such as v2.5.2, and the
    integration tool records no marker of which. The candidates are the
    merge-base of HEAD with origin/DEV and the nearest upstream release tag
    (three-part `vX.Y.Z[-suffix]`; the four-part Cosmyx release tags are
    excluded). The newest of them is the base: the other is its ancestor. When
    they have diverged, the base is ambiguous and None is returned.
    """
    candidates = []
    dev = git("merge-base", "HEAD", "origin/DEV")
    if dev.returncode == 0:
        candidates.append(dev.stdout.strip())
    tag = git("describe", "--tags", "--abbrev=0", "--match", "v[0-9]*", "--exclude", "v*.*.*.*", "HEAD")
    if tag.returncode == 0:
        candidates.append(git("rev-parse", f"{tag.stdout.strip()}^{{commit}}").stdout.strip())
    candidates = [c for c in candidates if c]
    if not candidates:
        return None
    best = candidates[0]
    for other in candidates[1:]:
        if git("merge-base", "--is-ancestor", best, other).returncode == 0:
            best = other
        elif git("merge-base", "--is-ancestor", other, best).returncode != 0:
            return None
    return best


def done(stdout: str = "", returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class FakeGh:
    """Answers the gh calls of prepare() from a small in-memory state."""

    def __init__(self, artifacts=RELEASE_ARTIFACTS, release=None, tag_ref=None, head="abc1234") -> None:
        self.artifacts = artifacts
        self.release = release
        self.tag_ref = tag_ref
        self.head = head
        self.calls: list[list[str]] = []

    def __call__(self, args):
        args = list(args)
        self.calls.append(args)
        if args[:2] == ["run", "view"]:
            return done(json.dumps({"headSha": self.head, "workflowName": "Build all"}))
        if args[0] == "api" and args[1] == "--paginate":
            return done("\n".join(self.artifacts) + "\n")
        if args[:2] == ["release", "view"]:
            return done(json.dumps(self.release)) if self.release is not None else done(returncode=1, stderr="not found")
        if args[0] == "api" and "/git/ref/tags/" in args[1]:
            return done(json.dumps(self.tag_ref)) if self.tag_ref is not None else done(returncode=1, stderr="404")
        if args[:2] == ["release", "create"]:
            return done("https://github.com/o/r/releases/tag/x")
        raise AssertionError(f"unexpected gh call {args}")

    def created(self) -> list[str] | None:
        return next((c for c in self.calls if c[:2] == ["release", "create"]), None)


class TagTests(unittest.TestCase):
    def test_release_tags_follow_v_base_dot_patch(self) -> None:
        self.assertEqual(rp.tag_display_version("v2.5.2.8"), "2.5.2-8")
        self.assertEqual(rp.tag_display_version("v2.10.0.12"), "2.10.0-12")

    def test_other_tags_are_refused(self) -> None:
        for tag in ("v3.0", "v4.0", "2.5.2.8", "v2.5.2", "v2.5.2-8", "v2.5.2.8-beta", "v02.5.2.8", "v2.5.2.８", ""):
            with self.subTest(tag=tag), self.assertRaises(rp.PublishError):
                rp.tag_display_version(tag)


class RunVersionTests(unittest.TestCase):
    def test_versions_come_from_the_cosmoslice_artifacts(self) -> None:
        self.assertEqual(rp.run_display_versions(RELEASE_ARTIFACTS), {"2.5.2-8"})

    def test_a_dev_build_cannot_be_published_as_a_release(self) -> None:
        dev = [n.replace("2.5.2-8", "2.6.0-dev-8") for n in RELEASE_ARTIFACTS]
        with self.assertRaises(rp.PublishError):
            rp.check_run_matches_tag("v2.6.0.8", dev)

    def test_the_tag_must_name_the_built_version(self) -> None:
        self.assertEqual(rp.check_run_matches_tag("v2.5.2.8", RELEASE_ARTIFACTS), "2.5.2-8")
        with self.assertRaises(rp.PublishError):
            rp.check_run_matches_tag("v2.5.2.9", RELEASE_ARTIFACTS)

    def test_a_run_without_cosmoslice_artifacts_is_refused(self) -> None:
        with self.assertRaises(rp.PublishError):
            rp.check_run_matches_tag("v2.5.2.8", ["OrcaSlicer_Windows_V2.5.2_x64", "PDB"])


class PrepareTests(unittest.TestCase):
    def test_a_missing_draft_is_created_on_the_run_commit(self) -> None:
        gh = FakeGh()
        rp.prepare("v2.5.2.8", "42", "o/r", gh)
        created = gh.created()
        self.assertIsNotNone(created)
        self.assertIn("--draft", created)
        self.assertNotIn("--prerelease", created)
        self.assertEqual(created[created.index("--target") + 1], "abc1234")
        self.assertEqual(created[created.index("--title") + 1], "CosmoSlice 2.5.2-8")

    def test_an_existing_draft_is_reused(self) -> None:
        gh = FakeGh(release={"isDraft": True, "isPrerelease": False})
        rp.prepare("v2.5.2.8", "42", "o/r", gh)
        self.assertIsNone(gh.created())

    def test_a_published_release_or_a_prerelease_is_refused(self) -> None:
        for state in ({"isDraft": False, "isPrerelease": False}, {"isDraft": True, "isPrerelease": True}):
            with self.subTest(state=state), self.assertRaises(rp.PublishError):
                rp.prepare("v2.5.2.8", "42", "o/r", FakeGh(release=state))

    def test_a_tag_on_another_commit_is_refused(self) -> None:
        gh = FakeGh(tag_ref={"object": {"type": "commit", "sha": "fff0000"}})
        with self.assertRaises(rp.PublishError):
            rp.prepare("v2.5.2.8", "42", "o/r", gh)
        self.assertIsNone(gh.created())

    def test_a_tag_on_the_run_commit_is_reused(self) -> None:
        gh = FakeGh(tag_ref={"object": {"type": "commit", "sha": "abc1234"}})
        rp.prepare("v2.5.2.8", "42", "o/r", gh)
        self.assertIsNotNone(gh.created())

    def test_a_wrong_tag_stops_before_any_gh_call(self) -> None:
        gh = FakeGh()
        with self.assertRaises(rp.PublishError):
            rp.prepare("v4.0", "42", "o/r", gh)
        self.assertEqual(gh.calls, [])

    def test_main_reports_an_error_as_exit_code_1(self) -> None:
        self.assertEqual(rp.main(["prepare", "--tag", "v4.0", "--run-id", "1", "--repo", "o/r"], FakeGh()), 1)


class DownloadTests(unittest.TestCase):
    def test_only_the_cosmoslice_release_artifacts_are_downloaded(self) -> None:
        calls = []
        rp.download("42", "o/r", Path("artifacts"), lambda args: calls.append(list(args)) or done())
        patterns = [calls[0][i + 1] for i, a in enumerate(calls[0]) if a == "-p"]
        self.assertEqual(patterns, list(rp.DOWNLOAD_PATTERNS))
        self.assertFalse(any("OrcaSlicer" in p for p in patterns))

    def test_the_windows_pattern_keeps_the_msix_out(self) -> None:
        from fnmatch import fnmatchcase

        windows = rp.DOWNLOAD_PATTERNS[0]
        self.assertTrue(fnmatchcase("CosmoSlice_Windows_2.5.2-8_4a8748a9_x64", windows))
        self.assertTrue(fnmatchcase("CosmoSlice_Windows_2.5.2-8_4a8748a9_x64_portable", windows))
        self.assertFalse(fnmatchcase("CosmoSlice_Windows_MSIX_2.5.2-8_4a8748a9_x64", windows))


class AssembleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.artifacts = self.root / "artifacts"
        files = {
            "CosmoSlice_Windows_2.5.2-8_4a8748a9_x64/CosmoSlice_Windows_Installer_2.5.2-8_x64.exe": "exe",
            "CosmoSlice_Windows_2.5.2-8_4a8748a9_x64_portable/orca-slicer.exe": "portable",
            "CosmoSlice_Windows_2.5.2-8_4a8748a9_x64_portable/resources/a.txt": "a",
            "CosmoSlice_Mac_universal_2.5.2-8_4a8748a9/CosmoSlice_Mac_universal_2.5.2-8_4a8748a9.dmg": "dmg",
            "CosmoSlice_Linux_ubuntu_2404_2.5.2-8_4a8748a9/CosmoSlice_Linux_AppImage_Ubuntu2404_2.5.2-8.AppImage": "ai",
            "CosmoSlice-Linux-flatpak_2.5.2-8_x86_64.flatpak/CosmoSlice-Linux-flatpak_2.5.2-8_x86_64.flatpak": "fp",
            "PDB/Debug_PDB_2.5.2-8.7z": "pdb",
        }
        for relative, content in files.items():
            path = self.artifacts / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_the_release_files_are_collected(self) -> None:
        names = rp.assemble(self.artifacts, self.root / "upload")
        self.assertEqual(
            names,
            sorted(
                [
                    "CosmoSlice_Windows_Installer_2.5.2-8_x64.exe",
                    "CosmoSlice_Windows_2.5.2-8_4a8748a9_x64_portable.zip",
                    "CosmoSlice_Mac_universal_2.5.2-8_4a8748a9.dmg",
                    "CosmoSlice_Linux_AppImage_Ubuntu2404_2.5.2-8.AppImage",
                    "CosmoSlice-Linux-flatpak_2.5.2-8_x86_64.flatpak",
                    "Debug_PDB_2.5.2-8.7z",
                ]
            ),
        )

    def test_the_portable_zip_holds_the_folder_contents(self) -> None:
        rp.assemble(self.artifacts, self.root / "upload")
        archive = self.root / "upload" / "CosmoSlice_Windows_2.5.2-8_4a8748a9_x64_portable.zip"
        with zipfile.ZipFile(archive) as zipped:
            names = {n.replace("\\", "/") for n in zipped.namelist()}
        self.assertIn("orca-slicer.exe", names)
        self.assertIn("resources/a.txt", names)

    def test_nothing_to_upload_is_an_error(self) -> None:
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(rp.PublishError):
            rp.assemble(empty, self.root / "upload-empty")


class WorkflowHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = WORKFLOW.read_text(encoding="utf-8").splitlines()

    def step_index(self, name: str) -> int:
        return self.lines.index(f"      - name: {name}")

    def test_prepare_runs_before_the_upstream_draft_check(self) -> None:
        prepare = next(i for i, l in enumerate(self.lines) if "release_publish.py prepare" in l)
        checkout = self.step_index("Cosmyx checkout # Cosmyx")
        self.assertLess(checkout, prepare)
        self.assertLess(prepare, self.step_index("Verify target is a draft release"))

    def test_the_upstream_download_and_assemble_steps_are_off(self) -> None:
        for name in ("Download release artifacts from build run", "Assemble release assets"):
            with self.subTest(step=name):
                index = self.step_index(name)
                self.assertTrue(self.lines[index + 1].startswith("        if: ${{ false }} # Cosmyx"))

    def test_the_cosmoslice_assets_are_assembled_before_the_upload(self) -> None:
        step = next(i for i, l in enumerate(self.lines) if "release_publish.py download" in l)
        self.assertIn("release_publish.py assemble", self.lines[step])
        self.assertGreater(step, self.step_index("Assemble release assets"))
        self.assertLess(step, self.step_index("Upload assets to draft release"))

    def test_no_product_name_in_the_upstream_file(self) -> None:
        # The branding engine applies the product name at build time; the hook
        # lines in this upstream file must name Cosmyx only (brand-check G7).
        for number, line in enumerate(self.lines, start=1):
            with self.subTest(line=number):
                self.assertNotIn("CosmoSlice", line)

    def test_every_added_line_is_tagged(self) -> None:
        base = upstream_base()
        if base is None:
            self.skipTest("no upstream base (origin/DEV or an upstream release tag) is an ancestor of HEAD")
        added = git("diff", "-U0", base, "--", WORKFLOW.relative_to(REPO_ROOT).as_posix())
        if added.returncode != 0:
            self.skipTest(f"cannot diff against the upstream base {base}: {added.stderr.strip()}")
        lines = [l[1:] for l in added.stdout.splitlines() if l.startswith("+") and not l.startswith("+++")]
        for line in lines:
            if line.strip():
                with self.subTest(line=line):
                    self.assertTrue(line.endswith("# Cosmyx") or "# Cosmyx:" in line)

if __name__ == "__main__":
    unittest.main()
