"""Checks of the branding recipe layout (decision 0120): branding.just holds
the engine recipes and imports one optional file per sub-task, so the
sub-task branches add their own file and never edit a shared one."""

from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
JUST_DIR = REPO_ROOT / "scripts" / "cosmyx" / "just"
BRANDING = JUST_DIR / "branding.just"

SUB_TASK_FILES = [
    "branding-logos.just",
    "branding-colours.just",
    "branding-candidates.just",
    "branding-product-name.just",
]

IMPORT = re.compile(r"^import\? '([^']+)'$", flags=re.MULTILINE)
RECIPE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)(?:\s[^:=]*)?:(?!=)", flags=re.MULTILINE)


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


if __name__ == "__main__":
    unittest.main()
