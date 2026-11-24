"""Checks of the branding recipe layout (decision 0120): branding.just holds
the engine recipes and imports one optional file per sub-task, so the
sub-task branches add their own file and never edit a shared one."""

from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest import mock

import branding_fixture

REPO_ROOT = Path(__file__).resolve().parents[3]
JUST_DIR = REPO_ROOT / "scripts" / "cosmyx" / "just"
BRANDING = JUST_DIR / "branding.just"
PREPARE_ACTION = REPO_ROOT / ".github" / "actions" / "cosmyx-prepare" / "action.yml"

SUB_TASK_FILES = [
    "branding-logos.just",
    "branding-colours.just",
    "branding-candidates.just",
    "branding-product-name.just",
]

IMPORT = re.compile(r"^import\? '([^']+)'$", flags=re.MULTILINE)
# A recipe header: its name, then optional parameters (defaults included), then a colon.
RECIPE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)(?:\s[^:\n]*)?:(?!=)", flags=re.MULTILINE)


def recipes(path: Path) -> list[str]:
    return RECIPE.findall(path.read_text(encoding="utf-8"))


class BrandingRecipeLayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = BRANDING.read_text(encoding="utf-8")
        self.imports = IMPORT.findall(self.text)

    def test_imports_every_sub_task_file_once(self) -> None:
        self.assertEqual(self.imports, SUB_TASK_FILES)

    def test_imports_close_the_file(self) -> None:
        # Recipes sit above the imports, so a new engine recipe never lands
        # next to an import line another branch might touch.
        last_line = self.text.rstrip("\n").splitlines()[-1]
        self.assertEqual(last_line, f"import? '{SUB_TASK_FILES[-1]}'")

    def test_every_branding_file_is_imported(self) -> None:
        present = sorted(path.name for path in JUST_DIR.glob("branding-*.just"))
        for name in present:
            with self.subTest(file=name):
                self.assertIn(name, self.imports)

    def test_sub_task_files_hold_no_import(self) -> None:
        for path in JUST_DIR.glob("branding-*.just"):
            with self.subTest(file=path.name):
                self.assertEqual(IMPORT.findall(path.read_text(encoding="utf-8")), [])

    def test_recipe_names_are_unique(self) -> None:
        seen: dict[str, str] = {}
        for path in [BRANDING, *sorted(JUST_DIR.glob("branding-*.just"))]:
            for name in recipes(path):
                with self.subTest(recipe=name):
                    self.assertNotIn(name, seen, f"{name} in {path.name} and {seen.get(name)}")
                seen[name] = path.name
        self.assertIn("brand-apply", seen)

    @unittest.skipIf(shutil.which("just") is None, "just is not installed on this machine")
    def test_just_lists_every_recipe(self) -> None:
        result = subprocess.run(
            ["just", "--summary"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        listed = set(result.stdout.split())
        for path in [BRANDING, *JUST_DIR.glob("branding-*.just")]:
            for name in recipes(path):
                with self.subTest(recipe=name):
                    self.assertIn(name, listed)


class PrepareProfileTest(unittest.TestCase):
    """The build legs run only the hermetic branding tests (see branding_fixture.PROFILE_ENV)."""

    def branding_test_step(self) -> str:
        steps = PREPARE_ACTION.read_text(encoding="utf-8").split("    - name: ")[1:]
        found = [step for step in steps if "test_branding_*.py" in step]
        self.assertEqual(len(found), 1, "exactly one prepare step runs the branding tests")
        return found[0]

    def test_prepare_action_exports_the_branding_mode_first(self) -> None:
        # The mode (strict unless the tree's upstream base is not DEV) is
        # chosen once and exported, so the real-tree tests and apply agree.
        steps = PREPARE_ACTION.read_text(encoding="utf-8").split("    - name: ")[1:]
        names = [step.splitlines()[0] for step in steps]
        mode = [index for index, step in enumerate(steps) if "branding/cli.py mode" in step]
        self.assertEqual(len(mode), 1, "exactly one prepare step exports the branding mode")
        self.assertIn('COSMYX_BRAND_MODE=', steps[mode[0]])
        self.assertIn('"$GITHUB_ENV"', steps[mode[0]])
        self.assertLess(mode[0], names.index("Test the graft, the worktree helper and the branding engine"))
        self.assertLess(mode[0], names.index("Apply Cosmyx branding"))

    def test_prepare_action_sets_the_profile_on_the_branding_tests(self) -> None:
        self.assertRegex(self.branding_test_step(), r"(?m)^\s+COSMYX_TEST_PROFILE: prepare$")

    def test_profile_is_read_from_the_environment(self) -> None:
        with mock.patch.dict("os.environ", {"COSMYX_TEST_PROFILE": "prepare"}):
            self.assertTrue(branding_fixture.prepare_profile())
        with mock.patch.dict("os.environ", {"COSMYX_TEST_PROFILE": "full"}):
            self.assertFalse(branding_fixture.prepare_profile())
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertFalse(branding_fixture.prepare_profile())

    def test_skip_in_prepare_skips_only_under_the_profile(self) -> None:
        def run(env: dict) -> unittest.TestResult:
            with mock.patch.dict("os.environ", env, clear=True):

                class Heavy(unittest.TestCase):
                    @branding_fixture.skip_in_prepare("needs docker")
                    def test_heavy(self) -> None:
                        pass

            result = unittest.TestResult()
            Heavy("test_heavy").run(result)
            return result

        skipped = run({"COSMYX_TEST_PROFILE": "prepare"}).skipped
        self.assertEqual(len(skipped), 1)
        self.assertIn("needs docker", skipped[0][1])
        self.assertEqual(run({}).skipped, [])


if __name__ == "__main__":
    unittest.main()
