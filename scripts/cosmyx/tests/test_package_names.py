"""Tests of the CI package names (decision 0210): scripts/cosmyx/package_names.py,
its table, the cosmyx-package-names action and the "# Cosmyx" hook steps that
call it."""

from __future__ import annotations

import io
import os
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "cosmyx"))

import package_names as pn  # noqa: E402

try:
    import branding  # noqa: E402
except ImportError:  # a tree without the branding engine
    branding = None

ACTION = REPO_ROOT / ".github" / "actions" / "cosmyx-package-names" / "action.yml"
BUILD_ORCA = REPO_ROOT / ".github" / "workflows" / "build_orca.yml"
BUILD_FLATPAK = REPO_ROOT / ".github" / "workflows" / "build_flatpak.yml"
# Older upstream bases have no build_flatpak.yml: their Flatpak job lives in
# build_all.yml, and the flatpak hook sits there.
BUILD_ALL = REPO_ROOT / ".github" / "workflows" / "build_all.yml"
# Tolerant on a tree whose upstream base is not DEV, detected like the branding
# (decision 0122): an anchor step that base does not have yet is skipped with a
# warning. Strict, DEV's mode, keeps failing on it.
TOLERANT = branding is not None and branding.brand_mode(os.environ, REPO_ROOT) == "tolerant"
DEV_TAG = "2.6.0-dev-8_aa9dac8"


class Workspace(unittest.TestCase):
    """A fake GitHub workspace; the repository root stays this checkout (the table)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self._tmp.name)
        self.commands: list[str] = []

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def touch(self, relative: str, data: bytes = b"x") -> Path:
        path = self.ws / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def env(self, os_name: str, **values: str) -> dict:
        env = {"RUNNER_OS": os_name, "GITHUB_WORKSPACE": str(self.ws)}
        env.update({f"COSMYX_PKG_{key}": value for key, value in values.items()})
        return env

    def run_stage(self, stage: str, env: dict) -> dict:
        return pn.run_stage(stage, REPO_ROOT, env, self.commands.append)


class TableTest(unittest.TestCase):
    def test_table_is_canonical_and_every_template_renders(self) -> None:
        path = REPO_ROOT / pn.TABLE
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(path.read_bytes().decode("utf-8").replace("\r\n", "\n"), json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        table = pn.load_table(REPO_ROOT)
        self.assertEqual((table["upstream"], table["product"]), ("OrcaSlicer", "CosmoSlice"))
        fields = {"ver": "V1", "arch": "_x64", "ubuntu": "2404", "ubuntu_str": "_Ubuntu2404"}
        for section in ("mac", "windows", "linux", "flatpak"):
            names = pn.Names(table, section, **fields)
            for key, template in names.templates.items():
                with self.subTest(section=section, key=key):
                    new = names.new(key)
                    if "{product}" in template:
                        self.assertIn("CosmoSlice", new)
                        self.assertNotIn("OrcaSlicer", new.replace("build/universal/OrcaSlicer", ""))
                        self.assertIn("OrcaSlicer", names.old(key))

    def test_validator_names_are_the_upstream_ones(self) -> None:
        table = pn.load_table(REPO_ROOT)
        mac = pn.Names(table, "mac", ver=DEV_TAG)
        self.assertEqual(mac.new("validator_artifact"), f"OrcaSlicer_profile_validator_Mac_universal_DMG_{DEV_TAG}")
        windows = pn.Names(table, "windows", ver=DEV_TAG, arch="_x64")
        self.assertEqual(windows.new("validator_artifact"), f"OrcaSlicer_profile_validator_Windows_{DEV_TAG}")

    def test_bad_schema_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / pn.TABLE).parent.mkdir(parents=True)
            (root / pn.TABLE).write_text('{"schema": 2, "upstream": "A", "product": "B"}', encoding="utf-8")
            with self.assertRaises(pn.PackageError):
                pn.load_table(root)


class WindowsTest(Workspace):
    def build(self, arch: str, tag: str, installer: bool = True, msix: bool = True) -> None:
        self.touch("build/OrcaSlicer/CosmoSlice.exe")
        if installer:
            cpack_arch = "_arm64" if "arm64" in arch else "_x64"
            self.touch(f"build/CosmoSlice_Windows_Installer_V2.6.0{cpack_arch}.exe")
        if msix:
            self.touch(f"build/OrcaSlicer_Windows_MSIX_{tag}{arch}.msix")

    def test_names_for_every_leg_and_tag(self) -> None:
        for arch in ("_x64", "_arm64", "_x64_msvc"):
            for tag in ("PR123", "V2.6.0", DEV_TAG):
                with self.subTest(arch=arch, tag=tag):
                    self.setUp()
                    self.build(arch, tag)
                    out = self.run_stage("windows", self.env("Windows", VER=tag, ARCH=arch, BUILD_DIR="build"))
                    self.assertEqual(out["portable_name"], f"CosmoSlice_Windows_{tag}{arch}_portable")
                    self.assertEqual(Path(out["portable_path"]), self.ws / "build" / "OrcaSlicer")
                    self.assertEqual(out["installer_name"], f"CosmoSlice_Windows_{tag}{arch}")
                    self.assertTrue(Path(out["installer_path"]).name.startswith("CosmoSlice_Windows_Installer_"))
                    self.assertEqual(out["msix_name"], f"CosmoSlice_Windows_MSIX_{tag}{arch}")
                    self.assertEqual(Path(out["msix_path"]).name, f"CosmoSlice_Windows_MSIX_{tag}{arch}.msix")
                    self.assertFalse((self.ws / f"build/OrcaSlicer_Windows_MSIX_{tag}{arch}.msix").exists())
                    self.assertEqual(out["delete"], [
                        f"OrcaSlicer_Windows_{tag}{arch}_portable", f"OrcaSlicer_Windows_{tag}{arch}",
                        f"OrcaSlicer_profile_validator_Windows_{tag}", f"OrcaSlicer_Windows_MSIX_{tag}{arch}",
                    ])
                    self.tearDown()

    def test_leg_without_installer_or_msix_uploads_the_portable_folder(self) -> None:
        self.build("_x64_msvc", DEV_TAG, installer=False, msix=False)
        out = self.run_stage("windows", self.env("Windows", VER=DEV_TAG, ARCH="_x64_msvc", BUILD_DIR="build"))
        self.assertEqual(sorted(out), ["delete", "portable_name", "portable_path"])
        self.assertIn(f"OrcaSlicer_profile_validator_Windows_{DEV_TAG}", out["delete"])

    def test_installer_with_the_upstream_name_fails(self) -> None:
        self.build("_x64", DEV_TAG, installer=False)
        self.touch("build/OrcaSlicer_Windows_Installer_V2.6.0_x64.exe")
        with self.assertRaisesRegex(pn.PackageError, "kept its upstream name"):
            self.run_stage("windows", self.env("Windows", VER=DEV_TAG, ARCH="_x64", BUILD_DIR="build"))

    def test_missing_portable_folder_fails(self) -> None:
        with self.assertRaises(pn.PackageError):
            self.run_stage("windows", self.env("Windows", VER=DEV_TAG, ARCH="_x64", BUILD_DIR="build"))

    def test_missing_version_fails(self) -> None:
        self.build("_x64", DEV_TAG)
        with self.assertRaisesRegex(pn.PackageError, "COSMYX_PKG_VER"):
            self.run_stage("windows", self.env("Windows", ARCH="_x64", BUILD_DIR="build"))

    def test_rerun_keeps_the_renamed_msix(self) -> None:
        self.build("_x64", DEV_TAG)
        env = self.env("Windows", VER=DEV_TAG, ARCH="_x64", BUILD_DIR="build")
        first = self.run_stage("windows", env)
        self.assertEqual(self.run_stage("windows", env), first)


class LinuxTest(Workspace):
    def test_appimage_renamed_and_validator_dropped(self) -> None:
        for arch in ("", "_aarch64"):
            for tag in ("PR-7", DEV_TAG):
                with self.subTest(arch=arch, tag=tag):
                    self.setUp()
                    self.touch(f"build/OrcaSlicer_Linux_AppImage_Ubuntu2404{arch}_{tag}.AppImage")
                    validator = self.touch("build/src/Release/OrcaSlicer_profile_validator")
                    env = self.env("Linux", VER=tag, ARCH=arch, UBUNTU="2404", UBUNTU_STR="_Ubuntu2404")
                    out = self.run_stage("linux", env)
                    self.assertEqual(out["appimage_name"], f"CosmoSlice_Linux_ubuntu_2404{arch}_{tag}")
                    self.assertEqual(Path(out["appimage_path"]), self.ws / f"build/CosmoSlice_Linux_AppImage_Ubuntu2404{arch}_{tag}.AppImage")
                    self.assertTrue(Path(out["appimage_path"]).is_file())
                    self.assertEqual(list((self.ws / "build").glob("OrcaSlicer_*.AppImage")), [])
                    self.assertFalse(validator.exists())
                    self.assertEqual(out["delete"], [f"OrcaSlicer_Linux_ubuntu_2404{arch}_{tag}"])
                    self.tearDown()

    def test_missing_appimage_fails(self) -> None:
        env = self.env("Linux", VER=DEV_TAG, ARCH="", UBUNTU="2404", UBUNTU_STR="_Ubuntu2404")
        with self.assertRaises(pn.PackageError):
            self.run_stage("linux", env)


class FlatpakTest(Workspace):
    def test_bundle_renamed_for_each_arch(self) -> None:
        for runner_arch, arch in (("X64", "x86_64"), ("ARM64", "aarch64")):
            with self.subTest(arch=arch):
                self.setUp()
                self.touch(f"OrcaSlicer-Linux-flatpak_V2.6.0_{arch}.flatpak")
                env = dict(self.env("Linux", VER="V2.6.0"), RUNNER_ARCH=runner_arch)
                out = self.run_stage("flatpak", env)
                self.assertEqual(out["flatpak_name"], f"CosmoSlice-Linux-flatpak_V2.6.0_{arch}.flatpak")
                self.assertTrue(Path(out["flatpak_path"]).is_file())
                self.assertEqual(out["delete"], [f"OrcaSlicer-Linux-flatpak_V2.6.0_{arch}.flatpak"])
                self.tearDown()

    def test_unknown_arch_fails(self) -> None:
        with self.assertRaises(pn.PackageError):
            self.run_stage("flatpak", dict(self.env("Linux", VER="V1"), RUNNER_ARCH="X86"))


class MacTest(Workspace):
    BUNDLE = "build/universal/OrcaSlicer"

    def universal(self) -> None:
        self.touch(f"{self.BUNDLE}/OrcaSlicer.app/Contents/MacOS/OrcaSlicer")
        self.touch(f"{self.BUNDLE}/OrcaSlicer_profile_validator.app/Contents/MacOS/OrcaSlicer_profile_validator")
        self.touch(f"OrcaSlicer_Mac_universal_{DEV_TAG}.dmg")
        self.touch(f"OrcaSlicer_profile_validator_Mac_universal_{DEV_TAG}.dmg")
        self.touch("build/universal/CosmoSlice_dmg/stale")

    def test_app_renamed_and_dmg_rebuilt_before_signing(self) -> None:
        self.universal()
        self.assertEqual(self.run_stage("mac-app", self.env("macOS", VER=DEV_TAG)), {})
        bundle = self.ws / self.BUNDLE
        self.assertEqual(sorted(path.name for path in bundle.iterdir()), ["CosmoSlice.app"])
        self.assertEqual(sorted(path.name for path in self.ws.glob("*.dmg")), [])  # the fake runner wrote none
        self.assertEqual(list((self.ws / "build/universal/CosmoSlice_dmg").iterdir()), [])
        # The renamed app is sealed and verified first, then made into the DMG.
        [seal, command] = self.commands
        # Paths are shell-quoted; on Windows the temp paths hold backslashes, so they get quotes.
        q = lambda path: shlex.quote(str(path))  # noqa: E731
        self.assertEqual(seal, pn.seal_command(bundle / "CosmoSlice.app"))
        self.assertIn(f"app={q(bundle / 'CosmoSlice.app')}", seal)
        staging = self.ws / "build/universal/CosmoSlice_dmg"
        self.assertIn(f"ditto {q(bundle / 'CosmoSlice.app')} {q(staging / 'CosmoSlice.app')}", command)
        self.assertIn("ln -s /Applications", command)
        self.assertIn("scripts/create_dmg.sh", command.replace("\\", "/"))
        self.assertTrue(command.endswith(f"create_dmg CosmoSlice {q(staging)} {q(self.ws / f'CosmoSlice_Mac_universal_{DEV_TAG}.dmg')}"))

    def test_rerun_after_rename_rebuilds_only(self) -> None:
        self.universal()
        env = self.env("macOS", VER=DEV_TAG)
        self.run_stage("mac-app", env)
        self.run_stage("mac-app", env)
        self.assertEqual(len(self.commands), 4)
        self.assertEqual(self.commands[0], self.commands[2])  # a rerun seals again

    def test_both_apps_present_fails(self) -> None:
        self.universal()
        self.touch(f"{self.BUNDLE}/CosmoSlice.app/Contents/MacOS/OrcaSlicer")
        with self.assertRaises(pn.PackageError):
            self.run_stage("mac-app", self.env("macOS", VER=DEV_TAG))

    def test_no_app_fails(self) -> None:
        (self.ws / self.BUNDLE).mkdir(parents=True)
        with self.assertRaises(pn.PackageError):
            self.run_stage("mac-app", self.env("macOS", VER=DEV_TAG))

    def test_per_arch_leg_does_nothing(self) -> None:
        # A push leg packs its bundle for the combine job: no DMG of its own, nothing renamed.
        app = self.touch("build/arm64/OrcaSlicer/OrcaSlicer.app/Contents/MacOS/OrcaSlicer")
        self.assertEqual(self.run_stage("mac-app", self.env("macOS", VER=DEV_TAG)), {})
        self.assertEqual(self.run_stage("mac-upload", self.env("macOS", VER=DEV_TAG)), {})
        self.assertEqual(self.commands, [])
        self.assertTrue(app.is_file())

    def test_pull_request_arch_dmg_renamed(self) -> None:
        # A pull request builds no universal app: each arch leg ships its own DMG.
        q = lambda path: shlex.quote(str(path))  # noqa: E731
        for arch in ("arm64", "x86_64"):
            with self.subTest(arch=arch):
                self.setUp()
                bundle = self.ws / f"build/{arch}/OrcaSlicer"
                self.touch(f"build/{arch}/OrcaSlicer/OrcaSlicer.app/Contents/MacOS/OrcaSlicer")
                self.touch(f"OrcaSlicer_Mac_{arch}_{DEV_TAG}.dmg")
                env = self.env("macOS", VER=DEV_TAG)
                self.assertEqual(self.run_stage("mac-app", env), {})
                self.assertEqual(sorted(path.name for path in bundle.iterdir()), ["CosmoSlice.app"])
                self.assertEqual(list(self.ws.glob("*.dmg")), [])
                [seal, command] = self.commands
                self.assertEqual(seal, pn.seal_command(bundle / "CosmoSlice.app"))
                staging = self.ws / f"build/{arch}/CosmoSlice_dmg"
                self.assertIn(f"ditto {q(bundle / 'CosmoSlice.app')} {q(staging / 'CosmoSlice.app')}", command)
                self.assertTrue(command.endswith(f"create_dmg CosmoSlice {q(staging)} {q(self.ws / f'CosmoSlice_Mac_{arch}_{DEV_TAG}.dmg')}"))
                self.touch(f"CosmoSlice_Mac_{arch}_{DEV_TAG}.dmg")  # what create_dmg writes
                out = self.run_stage("mac-upload", env)
                self.assertEqual(out["dmg_name"], f"CosmoSlice_Mac_{arch}_{DEV_TAG}")
                self.assertEqual(Path(out["dmg_path"]), self.ws / f"CosmoSlice_Mac_{arch}_{DEV_TAG}.dmg")
                self.assertEqual(out["delete"], [f"OrcaSlicer_Mac_{arch}_{DEV_TAG}"])
                self.tearDown()

    def test_pull_request_arch_upload_without_the_dmg_fails(self) -> None:
        self.touch("build/arm64/OrcaSlicer/OrcaSlicer.app/Contents/MacOS/OrcaSlicer")
        self.touch(f"OrcaSlicer_Mac_arm64_{DEV_TAG}.dmg")
        with self.assertRaisesRegex(pn.PackageError, "mac-app"):
            self.run_stage("mac-upload", self.env("macOS", VER=DEV_TAG))

    def test_upload_names_the_dmg_and_deletes_the_upstream_ones(self) -> None:
        (self.ws / self.BUNDLE).mkdir(parents=True)
        self.touch(f"CosmoSlice_Mac_universal_{DEV_TAG}.dmg")
        out = self.run_stage("mac-upload", self.env("macOS", VER=DEV_TAG))
        self.assertEqual(out["dmg_name"], f"CosmoSlice_Mac_universal_{DEV_TAG}")
        self.assertEqual(Path(out["dmg_path"]).name, f"CosmoSlice_Mac_universal_{DEV_TAG}.dmg")
        self.assertEqual(out["delete"], [f"OrcaSlicer_Mac_universal_{DEV_TAG}", f"OrcaSlicer_profile_validator_Mac_universal_DMG_{DEV_TAG}"])

    def test_upload_without_the_dmg_fails(self) -> None:
        (self.ws / self.BUNDLE).mkdir(parents=True)
        with self.assertRaisesRegex(pn.PackageError, "mac-app"):
            self.run_stage("mac-upload", self.env("macOS", VER=DEV_TAG))


class SealCommandTest(unittest.TestCase):
    """The seal command: keep a signature that verifies, refuse a broken
    identity signature, re-seal anything else ad hoc, then always verify."""

    def test_order_and_flags(self) -> None:
        command = pn.seal_command(Path("build") / "my app" / "CosmoSlice.app")
        self.assertTrue(command.startswith("set -e; "))
        self.assertIn(f"app={shlex.quote(str(Path('build') / 'my app' / 'CosmoSlice.app'))}", command)
        verify_first = command.index('codesign --verify --deep --strict "$app"')
        identity = command.index("grep -q '^Authority='")
        reseal = command.index('codesign --force --deep --sign - "$app"')
        final = command.rindex('codesign --verify --deep --strict --verbose=2 "$app"')
        self.assertLess(verify_first, identity)
        self.assertLess(identity, reseal)
        self.assertLess(reseal, final)
        self.assertTrue(command.endswith('codesign --verify --deep --strict --verbose=2 "$app"'))


@unittest.skipUnless(shutil.which("codesign") and shutil.which("ditto"), "codesign and ditto exist on macOS only")
class SealOnMacTest(unittest.TestCase):
    """A real bundle in the state the upstream unsigned build leaves it: a main
    executable carrying only its own ad-hoc (linker) signature and no sealed
    resources, which `codesign --verify` rejects and Gatekeeper calls damaged."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def unsealed_app(self) -> Path:
        app = self.root / "OrcaSlicer.app"
        (app / "Contents" / "MacOS").mkdir(parents=True)
        (app / "Contents" / "Resources").mkdir()
        (app / "Contents" / "Resources" / "data.txt").write_text("x", encoding="utf-8")
        (app / "Contents" / "Info.plist").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<plist version="1.0"><dict>'
            "<key>CFBundleExecutable</key><string>OrcaSlicer</string>"
            "<key>CFBundleIdentifier</key><string>com.example.dummy</string>"
            "<key>CFBundlePackageType</key><string>APPL</string></dict></plist>\n",
            encoding="utf-8",
        )
        # Sign the executable on its own, outside the bundle, like the linker does.
        exe = self.root / "OrcaSlicer"
        shutil.copyfile("/usr/bin/true", exe)
        subprocess.run(["codesign", "--remove-signature", str(exe)], check=True)
        subprocess.run(["codesign", "--force", "--sign", "-", "--identifier", "OrcaSlicer", str(exe)], check=True)
        exe.rename(app / "Contents" / "MacOS" / "OrcaSlicer")
        return app

    def verifies(self, app: Path) -> bool:
        return subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], capture_output=True).returncode == 0

    def test_renamed_unsealed_app_is_sealed_and_verifies(self) -> None:
        app = self.unsealed_app()
        renamed = app.with_name("CosmoSlice.app")
        app.rename(renamed)
        self.assertFalse(self.verifies(renamed))  # the reported bug
        pn.run_bash(pn.seal_command(renamed))
        self.assertTrue(self.verifies(renamed))
        copy = self.root / "staging" / "CosmoSlice.app"
        subprocess.run(["ditto", str(renamed), str(copy)], check=True)
        self.assertTrue(self.verifies(copy))  # the DMG copy keeps the seal

    def test_valid_signature_is_kept(self) -> None:
        app = self.unsealed_app()
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
        before = (app / "Contents" / "_CodeSignature" / "CodeResources").read_bytes()
        pn.run_bash(pn.seal_command(app))
        self.assertEqual((app / "Contents" / "_CodeSignature" / "CodeResources").read_bytes(), before)

    def test_app_changed_after_sealing_is_resealed(self) -> None:
        app = self.unsealed_app()
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
        (app / "Contents" / "Resources" / "data.txt").write_text("changed", encoding="utf-8")
        self.assertFalse(self.verifies(app))
        pn.run_bash(pn.seal_command(app))
        self.assertTrue(self.verifies(app))


class OtherLegTest(Workspace):
    def test_stages_do_nothing_on_another_os(self) -> None:
        for stage, os_name in (("mac-app", "Linux"), ("mac-upload", "Windows"), ("windows", "macOS"), ("linux", "Windows"), ("flatpak", "macOS")):
            with self.subTest(stage=stage):
                self.assertEqual(self.run_stage(stage, self.env(os_name)), {})


class CliTest(Workspace):
    def test_outputs_are_written_to_github_output(self) -> None:
        self.touch("OrcaSlicer-Linux-flatpak_V1_x86_64.flatpak")
        output = self.ws / "out.txt"
        env = dict(self.env("Linux", VER="V1"), RUNNER_ARCH="X64", GITHUB_OUTPUT=str(output))
        with redirect_stdout(io.StringIO()):
            self.assertEqual(pn.main(["flatpak", "--root", str(REPO_ROOT)], env=env, runner=self.commands.append), 0)
        text = output.read_text(encoding="utf-8")
        self.assertIn("flatpak_name=CosmoSlice-Linux-flatpak_V1_x86_64.flatpak\n", text)
        self.assertIn("delete<<COSMYX_EOF\nOrcaSlicer-Linux-flatpak_V1_x86_64.flatpak\nCOSMYX_EOF\n", text)

    def test_error_is_an_annotation_and_exit_1(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            code = pn.main(["linux", "--root", str(REPO_ROOT)], env=self.env("Linux", VER="V1", UBUNTU="2404", UBUNTU_STR="_U"))
        self.assertEqual(code, 1)
        self.assertIn("::error::package names (linux)", buffer.getvalue())

    def test_nothing_to_do_writes_nothing(self) -> None:
        output = self.ws / "out.txt"
        with redirect_stdout(io.StringIO()):
            self.assertEqual(pn.main(["windows", "--output", str(output)], env=self.env("Linux")), 0)
        self.assertEqual(output.read_text(encoding="utf-8"), "")


# ---------------------------------------------------------------- wiring


def step_names(text: str) -> list[str]:
    return [match.group(1).strip() for match in re.finditer(r"^\s*- name: (.+?)\s*$", text, re.MULTILINE)]


def hook_blocks(text: str) -> dict:
    """{stage: [lines]} of the cosmyx-package-names steps."""
    lines = text.replace("\r\n", "\n").split("\n")
    blocks = {}
    for index, line in enumerate(lines):
        if "uses: ./.github/actions/cosmyx-package-names" in line:
            block = lines[index - 1:index + 3]
            stage = re.search(r"stage: (\S+)", block[-1]).group(1)
            blocks[stage] = block
    return blocks


def job_text(text: str, job: str) -> str:
    """The lines of one top-level job of a workflow, "" when it has none."""
    lines = text.replace("\r\n", "\n").split("\n")
    start = next((index for index, line in enumerate(lines) if line.rstrip() == f"  {job}:"), None)
    if start is None:
        return ""
    end = next((index for index in range(start + 1, len(lines)) if re.match(r"^  \S", lines[index])), len(lines))
    return "\n".join(lines[start:end]) + "\n"


def flatpak_workflow() -> tuple:
    """(path, text) of the Flatpak build: build_flatpak.yml when the base has
    it, else the flatpak job of build_all.yml."""
    if BUILD_FLATPAK.is_file():
        return BUILD_FLATPAK, BUILD_FLATPAK.read_bytes().decode("utf-8")
    return BUILD_ALL, job_text(BUILD_ALL.read_bytes().decode("utf-8"), "flatpak")


class FlatpakWorkflowTest(unittest.TestCase):
    def test_the_flatpak_job_is_cut_out_of_build_all(self) -> None:
        text = "jobs:\r\n  linux:\r\n    - name: A\r\n  flatpak:\r\n    steps:\r\n      - name: B\r\n  later:\r\n    - name: C\r\n"
        self.assertEqual(step_names(job_text(text, "flatpak")), ["B"])
        self.assertEqual(job_text(text, "missing"), "")

    def test_the_flatpak_hook_file_is_found_on_this_base(self) -> None:
        path, text = flatpak_workflow()
        self.assertIn(path, (BUILD_FLATPAK, BUILD_ALL))
        self.assertIn("flatpak", hook_blocks(text))


class WiringTest(unittest.TestCase):
    def setUp(self) -> None:
        self.orca = BUILD_ORCA.read_bytes().decode("utf-8")
        self.flatpak_path, self.flatpak = flatpak_workflow()

    def anchor_index(self, names: list, anchor: str, step: str):
        """Where `anchor` sits, or None when a tolerant (non-DEV) base does not
        have that step yet: the check is skipped with a warning."""
        if TOLERANT and anchor not in names:
            print(f"warning: anchor skipped for {step!r}: {anchor!r} is absent on this upstream base", file=sys.stderr)
            return None
        return names.index(anchor)

    def assert_between(self, names: list, step: str, after: str | None, before: str | None) -> None:
        self.assertEqual(names.count(step), 1, step)
        position = names.index(step)
        if after and (index := self.anchor_index(names, after, step)) is not None:
            self.assertLess(index, position, f"{step} must come after {after}")
        if before and (index := self.anchor_index(names, before, step)) is not None:
            self.assertLess(position, index, f"{step} must come before {before}")

    def test_every_stage_has_one_hook(self) -> None:
        stages = sorted(list(hook_blocks(self.orca)) + list(hook_blocks(self.flatpak)))
        self.assertEqual(stages, sorted(pn.STAGES))

    def test_hooks_sit_at_their_anchors(self) -> None:
        names = step_names(self.orca)
        self.assert_between(names, "Cosmyx package names mac-app # Cosmyx", "Create DMG without notary", "Delete intermediate per-arch artifacts")
        # The rename goes before the Cosmyx signing, which signs and names the app it finds.
        for sign in (name for name in names if name.startswith("Cosmyx sign and notarize macOS")):
            self.assert_between(names, "Cosmyx package names mac-app # Cosmyx", None, sign)
        self.assert_between(names, "Cosmyx package names mac-upload # Cosmyx", "Upload OrcaSlicer_profile_validator DMG mac", "Deploy Mac release")
        # The per-arch (pull request) DMG is built and uploaded before both hooks.
        self.assert_between(names, "Cosmyx package names mac-app # Cosmyx", "Create DMG ${{ inputs.arch }} without notary", None)
        self.assert_between(names, "Cosmyx package names mac-upload # Cosmyx", "Upload DMG ${{ inputs.arch }}", None)
        self.assert_between(names, "Cosmyx package names windows # Cosmyx", "Build MSIX Store package Win", "Upload artifacts Win MSIX")
        self.assert_between(names, "Cosmyx package names windows # Cosmyx", "Upload OrcaSlicer_profile_validator Win", None)
        self.assert_between(names, "Cosmyx package names linux # Cosmyx", "Build orca_custom_preset_tests", "Upload artifacts Ubuntu")
        self.assert_between(names, "Cosmyx package names linux # Cosmyx", None, "Upload OrcaSlicer_profile_validator Ubuntu")
        flatpak = step_names(self.flatpak)
        self.assert_between(flatpak, "Cosmyx package names flatpak # Cosmyx", "Prepare Cosmyx sources # Cosmyx", "Upload artifacts Flatpak")

    def test_hooks_are_minimal_and_never_name_the_product(self) -> None:
        for text in (self.orca, self.flatpak):
            for stage, block in hook_blocks(text).items():
                with self.subTest(stage=stage):
                    self.assertTrue(all(line.endswith(" # Cosmyx") for line in block), block)
                    keys = [line.strip().lstrip("- ").split(":", 1)[0] for line in block]
                    self.assertEqual(keys, ["name", "uses", "with", "stage"])
                    self.assertNotIn("CosmoSlice", "\n".join(block))

    def test_hook_files_keep_their_line_endings(self) -> None:
        # A hook never mixes line endings into a file: every line of the
        # committed blob ends the same way. Both workflows are LF upstream on
        # DEV; an older base may keep build_all.yml CRLF, and only a tolerant
        # (non-DEV) run accepts that. The committed blob, not the checkout: a
        # Windows checkout (core.autocrlf) changes the line endings on disk
        # while the repository keeps its own.
        for path in (BUILD_ORCA, self.flatpak_path):
            relative = path.relative_to(REPO_ROOT).as_posix()
            blob = subprocess.run(
                ["git", "-C", str(REPO_ROOT), "cat-file", "blob", f":{relative}"],
                capture_output=True, check=True,
            ).stdout
            with self.subTest(path=path.name):
                lines = blob.split(b"\n")[:-1]
                crlf = [line.endswith(b"\r") for line in lines]
                self.assertTrue(all(crlf) or not any(crlf), f"{path.name} mixes LF and CRLF")
                if not TOLERANT:
                    self.assertNotIn(b"\r\n", blob, path.name)

    def test_action_uploads_every_output_and_deletes_the_rest(self) -> None:
        action = ACTION.read_text(encoding="utf-8")
        for package in ("dmg", "portable", "installer", "msix", "appimage", "flatpak"):
            with self.subTest(package=package):
                self.assertIn(f"steps.names.outputs.{package}_name", action)
                self.assertIn(f"steps.names.outputs.{package}_path", action)
        self.assertIn("geekyeggo/delete-artifact@v6", action)
        self.assertIn("steps.names.outputs.delete", action)
        self.assertIn("scripts/cosmyx/package_names.py", action)
        self.assertNotIn("CosmoSlice", action.split("runs:", 1)[1], "names come from packages.json, not the action")


if __name__ == "__main__":
    unittest.main()
