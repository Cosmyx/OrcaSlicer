"""Wiring of the GUI goldens: the two upstream hooks, the workflow, the
recipes, the Docker image pin, the goldens layout and the decisions."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = ROOT / ".github" / "workflows" / "cosmyx-gui-goldens.yml"
GUI = ROOT / "tests" / "cosmyx" / "gui"


class HookTests(unittest.TestCase):
    def test_gui_app_has_exactly_the_two_hook_lines(self) -> None:
        lines = (ROOT / "src" / "slic3r" / "GUI" / "GUI_App.cpp").read_text(encoding="utf-8").splitlines()
        golden = [i for i, line in enumerate(lines) if "golden" in line.lower()]
        self.assertEqual(len(golden), 2)
        include, call = (lines[i] for i in golden)
        self.assertEqual(include, '#include "Cosmyx/GoldenDriver.hpp" // Cosmyx')
        self.assertEqual(call, "            Cosmyx::start_golden_driver_if_requested(); // Cosmyx")
        # The include follows the other Cosmyx includes; the call follows post_init().
        self.assertTrue(lines[golden[0] - 1].endswith("// Cosmyx"))
        self.assertEqual(lines[golden[1] - 1], "            this->post_init();")
        self.assertEqual(lines[golden[1] + 1], "")

    def test_driver_is_a_no_op_without_the_variable(self) -> None:
        text = (ROOT / "src" / "slic3r" / "GUI" / "Cosmyx" / "GoldenDriver.cpp").read_text(encoding="utf-8")
        body = text[text.index("void start_golden_driver_if_requested()"):]
        self.assertIn("static bool started", body)
        self.assertIn('env("COSMYX_GUI_DRIVER_DIR")', body)
        self.assertLess(body.index("if (dir.empty())"), body.index("new Driver"))

    def test_driver_has_no_per_os_code(self) -> None:
        for name in ("GoldenDriver.cpp", "GoldenDriver.hpp", "logic/GoldenScript.cpp", "logic/GoldenScript.hpp"):
            text = (ROOT / "src" / "slic3r" / "GUI" / "Cosmyx" / name).read_text(encoding="utf-8")
            with self.subTest(file=name):
                self.assertNotRegex(text, r"#\s*if(def|ndef)?\s.*(_WIN32|__APPLE__|__linux__|__WXMSW__|__WXGTK__|__WXOSX__)")


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_triggers(self) -> None:
        self.assertIn('workflows: ["Build all"]', self.text)
        self.assertIn("types: [completed]", self.text)
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("schedule:", self.text)
        for name in ("run_id:", "mode:", "stability:"):
            self.assertIn(name, self.text)

    def test_status_context_and_states(self) -> None:
        self.assertEqual(self.text.count("context=cosmyx/gui-goldens"), 2)
        self.assertIn("state=pending", self.text)
        self.assertIn("Report only (MIXED)", self.text)
        self.assertIn("if: always() && needs.resolve.result == 'success'", self.text)

    def test_runners_and_trusted_tools(self) -> None:
        self.assertIn("runs-on: ${{ matrix.runner }}", self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertIn("CLI: tools/scripts/cosmyx/gui_goldens/cli.py", self.text)
        self.assertIn("docker build --platform linux/amd64 -t cosmyx-gui-goldens tools/tests/cosmyx/gui/docker", self.text)
        self.assertIn("Set-DisplayResolution -Width 1920 -Height 1080", self.text)
        self.assertIn("github.repository != 'OrcaSlicer/OrcaSlicer'", self.text)

    def test_untrusted_values_reach_scripts_through_env_only(self) -> None:
        for line in self.text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("run:", "gh ", "python", "docker")) and "${{" in stripped:
                self.fail(f"expression inside a script: {stripped}")

    def test_artifact_layout_matches_fetch(self) -> None:
        self.assertIn("name: cosmyx-gui-goldens-${{ matrix.os }}", self.text)
        self.assertIn("mkdir -p upload/images upload/report upload/logs", self.text)


class RecipeTests(unittest.TestCase):
    def test_recipes_have_comments(self) -> None:
        lines = (ROOT / "scripts" / "cosmyx" / "just" / "goldens.just").read_text(encoding="utf-8").splitlines()
        recipes = []
        for index, line in enumerate(lines):
            match = re.match(r"^([a-z][a-z0-9-]*)(\s+[A-Z_]+(=\"[^\"]*\")?)*\s*:(?!=)", line)
            if match:
                recipes.append(match.group(1))
                self.assertTrue(lines[index - 1].startswith("# "), match.group(1))
        self.assertEqual(recipes, ["goldens-gui", "goldens-gui-stability", "goldens-gui-fetch", "goldens-gui-review",
                                   "goldens-gui-local", "goldens-gui-status"])


class LayoutTests(unittest.TestCase):
    def test_docker_base_is_pinned_by_digest_and_snapshot(self) -> None:
        text = (GUI / "docker" / "Dockerfile").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^FROM ubuntu:24\.04@sha256:[0-9a-f]{64}$")
        self.assertRegex(text, r"ARG SNAPSHOT=\d{8}T\d{6}Z")
        for setting in ("LP_NUM_THREADS=1", "LP_NATIVE_VECTOR_WIDTH=128", "GALLIUM_DRIVER=llvmpipe", "GDK_BACKEND=x11"):
            self.assertIn(setting, text)

    def test_goldens_folders_and_attributes(self) -> None:
        for os_name in ("linux", "macos", "windows"):
            self.assertTrue((GUI / "goldens" / os_name).is_dir())
        attributes = (GUI / "goldens" / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("*.png binary", attributes)
        self.assertIn("*.txt text eol=lf", attributes)

    def test_decisions_are_recorded(self) -> None:
        decisions = ROOT / "wiki" / "decisions"
        for number in range(162, 179):
            with self.subTest(number=number):
                self.assertEqual(len(list(decisions.glob(f"{number:04d}-*.md"))), 1)
        english = next(decisions.glob("0176-*.md")).read_text(encoding="utf-8")
        self.assertIn("en_US", english)
        self.assertTrue((ROOT / "wiki" / "cosmyx" / "gui-goldens.md").is_file())


if __name__ == "__main__":
    unittest.main()
