"""seed (clean data folder) and launch (per-OS start of the built app)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gui_goldens import GoldenError, REPO_ROOT, launch, seed  # noqa: E402

VERSION_INC = 'set(SLIC3R_APP_NAME "OrcaSlicer")\nset(SLIC3R_APP_KEY "OrcaSlicer")\nset(SoftFever_VERSION "2.6.0-dev")\n'


class SeedTests(unittest.TestCase):
    def test_seeded_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            version_inc = Path(tmp) / "version.inc"
            version_inc.write_text(VERSION_INC, encoding="utf-8")
            datadir = Path(tmp) / "data"
            (datadir / "old").mkdir(parents=True)
            (datadir / "stale.txt").write_text("x", encoding="utf-8")
            config = seed.seed(datadir, version_inc)
            self.assertEqual(config.name, "OrcaSlicer.conf")
            self.assertEqual(sorted(p.name for p in datadir.iterdir()), ["OrcaSlicer.conf"])
            data = json.loads(config.read_text(encoding="utf-8"))
        app = data["app"]
        self.assertEqual(app["version"], "2.6.0-dev")
        self.assertEqual(app["language"], "en_US")
        self.assertIs(app["show_daily_tips"], False)
        self.assertIs(app["show_splash_screen"], False)
        self.assertEqual(app["version_check_url"], "http://127.0.0.1:9/")
        self.assertEqual(app["user_mode"], "expert")
        self.assertIs(data["firstguide"]["finish"], True)
        self.assertEqual(data["presets"]["machine"], "Voron 2.4 350 0.4 nozzle")

    def test_pinned_presets_ship_with_the_app(self) -> None:
        data = json.loads(seed.render(seed.TEMPLATE.read_text(encoding="utf-8"), "1.0.0"))
        profiles = REPO_ROOT / "resources" / "profiles"
        self.assertTrue((profiles / "Voron" / "machine" / f"{data['presets']['machine']}.json").is_file())
        self.assertTrue((profiles / "Voron" / "process" / f"{data['presets']['process']}.json").is_file())
        for name in data["presets"]["filaments"]:
            self.assertTrue((profiles / "OrcaFilamentLibrary" / "filament" / f"{name}.json").is_file())

    def test_bad_inputs(self) -> None:
        with self.assertRaises(GoldenError):
            seed.render('{"a": "@OTHER@"}', "1.0")
        with tempfile.TemporaryDirectory() as tmp:
            broken = Path(tmp) / "version.inc"
            broken.write_text("nothing", encoding="utf-8")
            with self.assertRaises(GoldenError):
                seed.identity(broken)


def ok(*args, **kwargs):
    return subprocess.CompletedProcess(args, 0, "", "")


class LaunchTests(unittest.TestCase):
    def test_linux_extracts_the_appimage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifacts, work = Path(tmp) / "a", Path(tmp) / "w"
            artifacts.mkdir()
            (artifacts / "OrcaSlicer_Linux.AppImage").write_bytes(b"x")

            def run(args, cwd=None, **kwargs):
                (Path(cwd) / "squashfs-root").mkdir()
                (Path(cwd) / "squashfs-root" / "AppRun").write_text("", encoding="utf-8")
                return ok(args)

            app = launch.prepare_linux(artifacts, work, run)
            self.assertTrue(app.command[0].endswith("AppRun"))

    def test_windows_copies_the_build_and_adds_mesa(self) -> None:
        # The branded name (package-name branding) and the upstream names are all accepted.
        for exe_name in launch.WINDOWS_EXES:
            with self.subTest(exe=exe_name), tempfile.TemporaryDirectory() as tmp:
                artifacts, work = Path(tmp) / "a", Path(tmp) / "w"
                (artifacts / "pkg").mkdir(parents=True)
                with zipfile.ZipFile(artifacts / "pkg" / "CosmoSlice_portable.zip", "w") as bundle:
                    bundle.writestr(f"CosmoSlice/{exe_name}", b"exe")
                fetched = []

                def fetch(dest: Path):
                    fetched.append(dest)
                    dest.mkdir(parents=True, exist_ok=True)
                    for name in ("opengl32.dll", "libgallium_wgl.dll"):
                        (dest / name).write_bytes(b"dll")
                    return dest, {"GALLIUM_DRIVER": "llvmpipe"}

                app = launch.prepare_windows(artifacts, work, fetch)
                # --sw-renderer would reach the command line parser, which rejects it.
                self.assertEqual(app.command, [str(work / "app" / exe_name)])
                self.assertEqual(app.process, Path(exe_name).stem)
                self.assertEqual(fetched, [work / "app" / "mesa"])
                self.assertEqual(app.env, {"GALLIUM_DRIVER": "llvmpipe"})
                for name in (exe_name, "opengl32.dll", "libgallium_wgl.dll"):
                    self.assertTrue((work / "app" / name).is_file(), name)

                def misplaced(dest: Path):
                    (work / "elsewhere").mkdir(exist_ok=True)
                    (work / "elsewhere" / "opengl32.dll").write_bytes(b"dll")
                    return work / "elsewhere", {}

                with self.assertRaises(GoldenError):
                    launch.prepare_windows(artifacts, work, misplaced)

    def test_windows_unpacked_build_prefers_the_branded_exe(self) -> None:
        def fetch(dest: Path):
            dest.mkdir(parents=True, exist_ok=True)
            (dest / "opengl32.dll").write_bytes(b"dll")
            return dest, {}

        for names, expected in ((("orca-slicer.exe",), "orca-slicer.exe"),
                                (("CosmoSlice.exe",), "CosmoSlice.exe"),
                                (("orca-slicer.exe", "CosmoSlice.exe"), "CosmoSlice.exe")):
            with self.subTest(names=names), tempfile.TemporaryDirectory() as tmp:
                artifacts, work = Path(tmp) / "a", Path(tmp) / "w"
                (artifacts / "build").mkdir(parents=True)
                for name in names:
                    (artifacts / "build" / name).write_bytes(b"exe")
                app = launch.prepare_windows(artifacts, work, fetch)
                self.assertEqual(Path(app.command[0]).name, expected)

    def test_windows_without_a_known_exe_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            artifacts, work = Path(tmp) / "a", Path(tmp) / "w"
            artifacts.mkdir()
            with zipfile.ZipFile(artifacts / "CosmoSlice_portable.zip", "w") as bundle:
                bundle.writestr("CosmoSlice/other.exe", b"exe")
            with self.assertRaises(GoldenError):
                launch.prepare_windows(artifacts, work, lambda dest: (dest, {}))

    def test_macos_finds_the_bundle_under_either_name(self) -> None:
        for bundle in ("CosmoSlice.app", "OrcaSlicer.app"):
            with self.subTest(bundle=bundle), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / bundle).mkdir()
                (root / "OrcaSlicer_profile_validator.app").mkdir()
                self.assertEqual(launch.find_app(root).name, bundle)

    def test_one_artifact_is_expected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(GoldenError):
                launch.prepare_linux(Path(tmp), Path(tmp) / "w", ok)

    def test_driver_environment_and_command(self) -> None:
        env = launch.driver_env({"PATH": "p"}, Path("d"), Path("s.json"), "linux")
        self.assertEqual(env["COSMYX_GUI_DRIVER_DIR"], "d")
        self.assertEqual(env["COSMYX_GUI_DRIVER_SCRIPT"], "s.json")
        self.assertEqual(env["COSMYX_GUI_DRIVER_OS"], "linux")
        self.assertEqual(env["LANG"], "en_US.UTF-8")
        self.assertEqual(launch.command(launch.App(["app"], "app"), Path("data")), ["app", "--datadir", "data"])

    def test_display_is_started_only_without_one(self) -> None:
        started = []
        popen = lambda args, env=None: started.append(args[0]) or args[0]
        env: dict[str, str] = {}
        launch.start_display(env, popen=popen, sleep=lambda s: None)
        self.assertEqual(started, ["Xvfb", "openbox"])
        self.assertEqual(env["DISPLAY"], ":99")
        self.assertEqual(launch.start_display({"DISPLAY": ":0"}, popen=popen, sleep=lambda s: None), [])
        self.assertEqual(launch.start_display_for("windows", {}, popen=popen, sleep=lambda s: None), [])


if __name__ == "__main__":
    unittest.main()
