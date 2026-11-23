"""cli: the workflow plan (resolve), golden updates, stability, the UI slice
G-code check (T13 slice.py, faked here)."""

from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from gui_goldens import cli, compare, png  # noqa: E402

TAG = "2.6.0-dev-8_abc1234"
NAMES = [f"OrcaSlicer_Windows_{TAG}_x64_portable", f"OrcaSlicer_Windows_{TAG}_x64_msvc_portable",
         f"OrcaSlicer_Windows_{TAG}_arm64_portable", f"OrcaSlicer_Mac_universal_{TAG}", f"OrcaSlicer_Mac_arm64_{TAG}",
         f"OrcaSlicer_Linux_ubuntu_2404_{TAG}", f"OrcaSlicer_Linux_ubuntu_2404_aarch64_{TAG}"]


@dataclass
class FakeArtifact:
    name: str
    family: str
    arch: str = ""
    msvc: bool = False


def classify(name: str):
    """Same families as artifact_checks/data/expectations.json (T13)."""
    if "_Windows_" in name and name.endswith("_portable"):
        arch = "arm64" if "_arm64" in name else "x64"
        return FakeArtifact(name, "windows-portable", arch, "_msvc" in name)
    if "_Mac_universal_" in name:
        return FakeArtifact(name, "mac-universal")
    if "_Mac_arm64_" in name:
        return FakeArtifact(name, "mac-arm64")
    if "_Linux_ubuntu_" in name:
        return FakeArtifact(name, "linux-appimage", "aarch64" if "aarch64" in name else "x86_64")
    return None


def build_run(conclusion="success", branch="DEV", fork=False) -> dict:
    return {"head_sha": "a" * 40, "head_branch": branch, "conclusion": conclusion,
            "repository": {"full_name": "Cosmyx/OrcaSlicer"},
            "head_repository": {"full_name": "someone/OrcaSlicer" if fork else "Cosmyx/OrcaSlicer"}}


class ResolveTests(unittest.TestCase):
    def resolve(self, run=None, names=NAMES, changed=(), mode="compare", stability="auto", event="workflow_run"):
        return cli.resolve(run or build_run(), [{"name": n} for n in names], list(changed), mode, stability, event,
                           classify)

    def test_one_artifact_per_os(self) -> None:
        picked = cli.pick_artifacts(NAMES, classify)
        self.assertEqual(picked, {"windows": NAMES[0], "macos": NAMES[3], "linux": NAMES[5]})
        self.assertEqual(cli.pick_artifacts(NAMES[4:5], classify), {"macos": NAMES[4]})

    def test_branded_artifact_names_are_picked_too(self) -> None:
        # Package-name branding renames the artifacts from OrcaSlicer_ to CosmoSlice_.
        branded = [n.replace("OrcaSlicer_", "CosmoSlice_", 1) for n in NAMES]
        self.assertEqual(cli.pick_artifacts(branded, classify),
                         {"windows": branded[0], "macos": branded[3], "linux": branded[5]})

    def test_a_good_build_runs_on_every_os(self) -> None:
        outputs = self.resolve()
        self.assertEqual(outputs["run_ok"], "true")
        self.assertEqual([m["os"] for m in json.loads(outputs["matrix"])], ["linux", "macos", "windows"])
        self.assertEqual(json.loads(outputs["matrix"])[2]["runner"], "windows-2025")
        self.assertEqual(outputs["passes"], "1")
        self.assertEqual(outputs["report_only"], "false")

    def test_reasons_not_to_run(self) -> None:
        failed = self.resolve(run=build_run(conclusion="failure"))
        self.assertEqual((failed["run_ok"], failed["matrix"]), ("false", "[]"))
        self.assertIn("failure", failed["reason"])
        fork = self.resolve(run=build_run(fork=True))
        self.assertEqual((fork["run_ok"], fork["matrix"]), ("false", "[]"))
        partial = self.resolve(names=NAMES[3:4])
        self.assertEqual(partial["run_ok"], "false")
        self.assertIn("linux, windows", partial["reason"])

    def test_mixed_only_reports(self) -> None:
        self.assertEqual(self.resolve(run=build_run(branch="MIXED"))["report_only"], "true")

    def test_when_the_second_pass_runs(self) -> None:
        self.assertEqual(self.resolve(changed=["src/slic3r/GUI/Plater.cpp"])["passes"], "1")
        for changed in (["tests/cosmyx/gui/script.json"], ["scripts/cosmyx/gui_goldens/png.py"],
                        ["src/slic3r/GUI/Cosmyx/GoldenDriver.cpp"], ["src/slic3r/GUI/Cosmyx/logic/GoldenScript.cpp"]):
            with self.subTest(changed=changed):
                self.assertEqual(self.resolve(changed=changed)["passes"], "2")
        self.assertEqual(self.resolve(mode="update")["passes"], "2")
        self.assertEqual(self.resolve(event="schedule")["passes"], "2")
        self.assertEqual(self.resolve(stability="on")["passes"], "2")
        self.assertEqual(self.resolve(stability="off", mode="update")["passes"], "1")


def image(value: int) -> png.Image:
    return png.Image(2, 2, bytes((value, value, value, 255)) * 4)


class UpdateTests(unittest.TestCase):
    def test_only_failed_new_and_gone_goldens_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            goldens, actual = Path(tmp) / "g", Path(tmp) / "a"
            png.write(goldens / "00-keep.png", image(1))
            png.write(goldens / "10-fail.png", image(1))
            png.write(goldens / "20-gone.png", image(1))
            png.write(actual / "00-keep.png", image(2))  # a pass within tolerance keeps the golden
            png.write(actual / "10-fail.png", image(3))
            png.write(actual / "30-new.png", image(4))
            (actual / "environment.json").write_text("{}\n", encoding="utf-8")
            data = {"results": [{"name": "00-keep.png", "status": "pass"}, {"name": "10-fail.png", "status": "fail"},
                                {"name": "20-gone.png", "status": "gone"}, {"name": "30-new.png", "status": "missing"},
                                {"name": "90-slice-gcode", "status": "fail"}]}
            changed = cli.update(goldens, actual, data)
            self.assertEqual(changed, ["10-fail.png", "20-gone.png", "30-new.png"])
            self.assertEqual(png.read(goldens / "00-keep.png"), image(1))
            self.assertEqual(png.read(goldens / "10-fail.png"), image(3))
            self.assertFalse((goldens / "20-gone.png").exists())
            self.assertTrue((goldens / "environment.json").is_file())


class StabilityTests(unittest.TestCase):
    def test_a_surface_seen_by_one_pass_only_is_unstable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Path(tmp) / "1", Path(tmp) / "2"
            png.write(first / "00-a.png", image(1))
            png.write(second / "00-a.png", image(1))
            png.write(first / "10-b.png", image(1))
            results = {r.name: r.status for r in cli.stability_results(first, second, compare.Tolerance())}
        self.assertEqual(results, {"00-a.png": "pass", "10-b.png": "fail"})


class GcodeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.version_inc = Path(self.tmp.name) / "version.inc"
        self.version_inc.write_text('set(SLIC3R_APP_NAME "OrcaSlicer")\nset(SoftFever_VERSION "2.6.0-dev")\n',
                                    encoding="utf-8")
        self.gcode = Path(self.tmp.name) / "plate_1.gcode"

    def fake_slice(self, problems: list[str]) -> None:
        module = types.ModuleType("artifact_checks.slice")
        module.header_identity = lambda text: ("OrcaSlicer", "2.6.0-dev")
        module.gcode_problems = lambda text, name, version, min_g1: problems
        package = types.ModuleType("artifact_checks")
        package.slice = module
        saved = {name: sys.modules.get(name) for name in ("artifact_checks", "artifact_checks.slice")}
        sys.modules.update({"artifact_checks": package, "artifact_checks.slice": module})
        self.addCleanup(lambda: [sys.modules.pop(n, None) if v is None else sys.modules.__setitem__(n, v)
                                 for n, v in saved.items()])

    def test_no_gcode_written_fails(self) -> None:
        self.assertEqual(cli.gcode_results(self.gcode, self.version_inc)[0].status, "fail")
        self.assertEqual(cli.gcode_results(None, self.version_inc), [])

    def test_gcode_is_judged_by_the_t13_checks(self) -> None:
        self.gcode.write_text("; HEADER_BLOCK_START\n", encoding="utf-8")
        self.fake_slice([])
        self.assertEqual(cli.gcode_results(self.gcode, self.version_inc)[0].status, "pass")
        self.fake_slice(["no ';TYPE:' feature marker"])
        result = cli.gcode_results(self.gcode, self.version_inc)[0]
        self.assertEqual(result.status, "fail")
        self.assertIn("TYPE", result.reason)


if __name__ == "__main__":
    unittest.main()
