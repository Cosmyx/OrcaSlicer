"""Checks of the Cosmyx foundation files: justfile, changelog, decisions and
the script test runner."""

from __future__ import annotations

import importlib.util
import io
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path, PurePosixPath

COSMYX_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = COSMYX_DIR.parents[1]


def load_module(name: str):
    """Import a script of scripts/cosmyx by file name."""
    spec = importlib.util.spec_from_file_location(name, COSMYX_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


decisions = load_module("decisions")
run_script_tests = load_module("run_script_tests")
workflow_jobs = load_module("workflow_jobs")


class JustfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (REPO_ROOT / "justfile").read_text(encoding="utf-8")

    def test_every_import_points_under_scripts_cosmyx_just(self) -> None:
        imports = re.findall(r"^import\??\s+'([^']+)'", self.text, flags=re.MULTILINE)
        self.assertTrue(imports, "the justfile imports no feature recipes")
        for target in imports:
            path = PurePosixPath(target)
            with self.subTest(target=target):
                self.assertEqual(path.parent, PurePosixPath("scripts/cosmyx/just"))
                self.assertEqual(path.suffix, ".just")
                self.assertTrue(self.text_has_optional_import(target))

    def text_has_optional_import(self, target: str) -> bool:
        # Feature recipe files are created by their own task, so every import
        # must be optional for the justfile to load before they exist.
        return f"import? '{target}'" in self.text

    def test_every_recipe_has_a_comment(self) -> None:
        lines = self.text.splitlines()
        for index, line in enumerate(lines):
            match = re.match(r"^([a-z][a-z0-9-]*)(\s+[A-Z_]+)*\s*:(?!=)", line)
            if match is None:
                continue
            with self.subTest(recipe=match.group(1)):
                self.assertGreater(index, 0)
                self.assertTrue(lines[index - 1].startswith("# "))

    def test_planned_feature_imports_are_present(self) -> None:
        for name in (
            "branding", "goldens", "i18n", "macos-signing", "signing", "sync", "tests", "version",
        ):
            with self.subTest(name=name):
                self.assertTrue(self.text_has_optional_import(f"scripts/cosmyx/just/{name}.just"))

    def test_foundation_recipes_exist(self) -> None:
        for recipe in ("default", "test-scripts", "build-all", "build-status", "decisions"):
            with self.subTest(recipe=recipe):
                self.assertRegex(self.text, rf"(?m)^{re.escape(recipe)}\b[^:\n]*:")


SLOTS_BY_AREA = {
    "repo": ["T0"],
    "libslic3r": ["T1", "T2", "T3", "T4"],
    "GUI": ["T5", "T6", "T7", "T11b", "T11c", "T11d", "T11e", "T11f", "T28", "T26"],
    "i18n": ["T8"],
    "CI-release": ["T9", "T10", "T11a", "T13", "T15"],
}


class ChangelogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    def test_every_planned_task_has_one_slot(self) -> None:
        for slots in SLOTS_BY_AREA.values():
            for task in slots:
                with self.subTest(task=task):
                    self.assertEqual(self.text.count(f"<!-- cosmyx-slot: {task} -->"), 1)

    def test_slots_are_blank_line_separated(self) -> None:
        lines = self.text.splitlines()
        for index, line in enumerate(lines):
            if not line.startswith("<!-- cosmyx-slot:"):
                continue
            with self.subTest(slot=line):
                self.assertEqual(lines[index - 1], "")

    def test_areas_are_in_order(self) -> None:
        areas = re.findall(r"^### (.+)$", self.text, flags=re.MULTILINE)
        self.assertEqual(areas[:5], ["repo", "libslic3r", "GUI", "i18n", "CI-release"])

    def test_slots_sit_in_their_area(self) -> None:
        expected = SLOTS_BY_AREA
        sections = re.split(r"^### ", self.text, flags=re.MULTILINE)[1:]
        found = {}
        for section in sections:
            name = section.splitlines()[0].strip()
            found[name] = re.findall(r"<!-- cosmyx-slot: (T\d+[a-z]?) -->", section)
        for area, slots in expected.items():
            with self.subTest(area=area):
                self.assertEqual(found.get(area), slots)


class DecisionSlotTests(unittest.TestCase):
    def test_slot_decision_lists_every_marker(self) -> None:
        text = (REPO_ROOT / "wiki" / "decisions" / "0003-changelog-slots.md").read_text(encoding="utf-8")
        for area, slots in SLOTS_BY_AREA.items():
            with self.subTest(area=area):
                self.assertIn(f"- `{area}`: {', '.join(slots)}.", text)


class ChecksWorkflowTests(unittest.TestCase):
    def test_paths_cover_cosmyx_owned_files(self) -> None:
        text = (REPO_ROOT / ".github" / "workflows" / "cosmyx-checks.yml").read_text(encoding="utf-8")
        required = (
            "justfile", "CHANGELOG.md", "scripts/cosmyx/**", "wiki/**",
            ".github/workflows/cosmyx-checks.yml", "cosmyx-src/**", ".github/actions/**",
            ".github/cosmyx/**", ".github/workflows/cosmyx-*.yml",
            "localization/cosmyx/**", "scripts/sign_windows.ps1",
            ".github/workflows/build_orca.yml", ".github/workflows/build_flatpak.yml",
        )
        for path in required:
            with self.subTest(path=path):
                # Listed once under pull_request and once under push.
                self.assertEqual(text.count(f"      - '{path}'\n"), 2)

    def test_paths_drop_the_unused_root_cosmyx_folder(self) -> None:
        # No branch ships a root cosmyx/ folder; Cosmyx sources live in cosmyx-src/.
        text = (REPO_ROOT / ".github" / "workflows" / "cosmyx-checks.yml").read_text(encoding="utf-8")
        self.assertNotIn("      - 'cosmyx/**'\n", text)


class FlatpakTestTargetTests(unittest.TestCase):
    def test_cosmyx_tests_hangs_on_a_target_the_flatpak_builds(self) -> None:
        # The flatpak leg builds an explicit target list; a registered suite
        # outside it shows up in ctest as <target>_NOT_BUILT and fails the leg.
        cmake = (REPO_ROOT / "tests" / "cosmyx" / "CMakeLists.txt").read_text(encoding="utf-8")
        manifest = (REPO_ROOT / "scripts" / "flatpak" / "com.orcaslicer.OrcaSlicer.yml").read_text(encoding="utf-8")
        built = {
            name
            for targets in re.findall(r"--target\s+((?:[\w-]+\s+)+)", manifest)
            for name in targets.split()
            if name.endswith("_tests")
        }
        self.assertTrue(built, "the flatpak manifest lists no test targets")
        if "cosmyx_tests" in built:
            return
        hooks = set(re.findall(r"add_dependencies\((\w+)\s+\$\{_TEST_NAME\}_tests\)", cmake))
        self.assertTrue(hooks & built, f"cosmyx_tests is built by none of {sorted(built)}")


class FlatpakTestAssetTests(unittest.TestCase):
    def test_asset_keeps_the_resources_cosmyx_tests_reads(self) -> None:
        # The flatpak leg deletes every resources/ folder its filter does not
        # name; cosmyx_tests reads resources/cosmyx and resources/info. The
        # job lives in build_flatpak.yml or, on older bases, in build_all.yml.
        found = workflow_jobs.find_job(REPO_ROOT, "flatpak")
        if found is None:
            self.skipTest("this upstream base has no flatpak build job")
        body = found[2]["flatpak"]
        filters = [line for line in body.splitlines() if 'find "$d/resources" ' in line and "rm -rf" in line]
        self.assertEqual(len(filters), 1, "expected one resources/ filter in the test asset step")
        kept = set(re.findall(r"! -name (\S+)", filters[0]))
        for folder in ("cosmyx", "info", "profiles", "printers", "images"):
            with self.subTest(folder=folder):
                self.assertIn(folder, kept)


class DecisionTests(unittest.TestCase):
    def test_register_is_valid(self) -> None:
        found, errors = decisions.list_decisions(decisions.DECISIONS_DIR)
        self.assertEqual(errors, [])
        numbers = [number for number, _, _ in found]
        for number in ("0001", "0002", "0003", "0004"):
            self.assertIn(number, numbers)

    def test_bad_names_and_duplicates_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "README.md").write_text("# Register\n", encoding="utf-8")
            (directory / "0010-good-one.md").write_text("# 0010. Good one\n", encoding="utf-8")
            (directory / "0010-same-number.md").write_text("# 0010. Same number\n", encoding="utf-8")
            (directory / "11-Bad Name.md").write_text("# Bad\n", encoding="utf-8")
            (directory / "0012-no-title.md").write_text("no heading\n", encoding="utf-8")
            found, errors = decisions.list_decisions(directory)
        self.assertEqual([name for _, _, name in found], ["0010-good-one.md", "0010-same-number.md"])
        self.assertEqual(found[0][1], "Good one")
        self.assertIn("bad file name: 11-Bad Name.md", errors)
        self.assertIn("no title: 0012-no-title.md", errors)
        self.assertIn("duplicate number: 0010", errors)


class RunnerTests(unittest.TestCase):
    def run_pester(self, *, with_file: bool, powershell, require: bool) -> tuple[bool, str]:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            if with_file:
                (directory / "Sample.Tests.ps1").write_text("Describe 'x' {}\n", encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                ok = run_script_tests.run_pester_tests(directory, powershell, require)
        return ok, out.getvalue() + err.getvalue()

    def test_no_pester_files_is_a_pass(self) -> None:
        ok, output = self.run_pester(with_file=False, powershell=None, require=True)
        self.assertTrue(ok)
        self.assertIn("nothing to run", output)

    def test_missing_powershell_skips_with_a_message(self) -> None:
        ok, output = self.run_pester(with_file=True, powershell=None, require=False)
        self.assertTrue(ok)
        self.assertIn("Pester skipped", output)

    def test_missing_powershell_fails_when_required(self) -> None:
        ok, output = self.run_pester(with_file=True, powershell=None, require=True)
        self.assertFalse(ok)
        self.assertIn("required", output)


if __name__ == "__main__":
    unittest.main()
