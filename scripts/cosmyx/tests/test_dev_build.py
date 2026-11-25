"""The Cosmyx dev build: OS selection, package version, DMG plan and the
workflow wiring (decision 0218)."""

from __future__ import annotations

import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "cosmyx" / "ci"))

import dev_build  # noqa: E402

WORKFLOWS = REPO_ROOT / ".github" / "workflows"
WORKFLOW = WORKFLOWS / "cosmyx-dev-build.yml"


def pr_event(labels: list[str], action: str = "opened", label: str | None = None, number: int = 7) -> dict:
    event = {
        "action": action,
        "pull_request": {"number": number, "head": {"sha": "abcdef1234567890"},
                         "labels": [{"name": name} for name in labels]},
    }
    if label is not None:
        event["label"] = {"name": label}
    return event


def targets(event_name: str, event: dict) -> list[str]:
    return dev_build.select(event_name, event)["targets"]


class PullRequestSelectionTests(unittest.TestCase):
    def test_no_build_label_builds_the_defaults(self) -> None:
        self.assertEqual(targets("pull_request", pr_event([])), ["linux", "windows", "macos-arm64"])

    def test_each_label_alone_builds_only_its_os(self) -> None:
        for target in dev_build.TARGETS:
            with self.subTest(target=target):
                self.assertEqual(targets("pull_request", pr_event([f"build:{target}"])), [target])

    def test_labels_combine_in_a_fixed_order(self) -> None:
        chosen = dev_build.select("pull_request", pr_event(["build:macos-x86_64", "build:linux", "build:macos-arm64"]))
        self.assertEqual(chosen["targets"], ["linux", "macos-arm64", "macos-x86_64"])
        self.assertEqual(chosen["macos_archs"], ["arm64", "x86_64"])

    def test_other_labels_are_ignored(self) -> None:
        self.assertEqual(targets("pull_request", pr_event(["bug", "RDY2MERGE", "build:windows"])), ["windows"])
        self.assertEqual(targets("pull_request", pr_event(["bug"])), list(dev_build.DEFAULT_TARGETS))

    def test_unknown_build_label_fails(self) -> None:
        with self.assertRaisesRegex(dev_build.SelectError, "build:mac"):
            dev_build.select("pull_request", pr_event(["build:mac"]))

    def test_non_build_label_event_builds_nothing(self) -> None:
        for action in ("labeled", "unlabeled"):
            with self.subTest(action=action):
                chosen = dev_build.select("pull_request", pr_event(["bug"], action=action, label="bug"))
                self.assertFalse(chosen["build"])
                self.assertEqual(chosen["targets"], [])

    def test_build_label_event_builds_the_current_labels(self) -> None:
        added = dev_build.select("pull_request", pr_event(["build:linux"], action="labeled", label="build:linux"))
        self.assertEqual(added["targets"], ["linux"])
        removed = dev_build.select("pull_request", pr_event([], action="unlabeled", label="build:linux"))
        self.assertEqual(removed["targets"], list(dev_build.DEFAULT_TARGETS))

    def test_other_events_fail(self) -> None:
        with self.assertRaises(dev_build.SelectError):
            dev_build.select("push", {})


class DispatchSelectionTests(unittest.TestCase):
    def test_defaults_match_the_form(self) -> None:
        self.assertEqual(targets("workflow_dispatch", {"inputs": {}}), ["linux", "windows", "macos-arm64"])

    def test_inputs_as_strings_or_booleans(self) -> None:
        event = {"inputs": {"linux": "false", "windows": False, "macos-arm64": "true", "macos-x86_64": True}}
        chosen = dev_build.select("workflow_dispatch", event)
        self.assertEqual(chosen["targets"], ["macos-arm64", "macos-x86_64"])
        self.assertEqual(chosen["macos_archs"], ["arm64", "x86_64"])

    def test_each_checkbox_alone(self) -> None:
        for target in dev_build.TARGETS:
            with self.subTest(target=target):
                inputs = {name: str(name == target).lower() for name in dev_build.TARGETS}
                self.assertEqual(targets("workflow_dispatch", {"inputs": inputs}), [target])

    def test_nothing_ticked_fails(self) -> None:
        inputs = {name: "false" for name in dev_build.TARGETS}
        with self.assertRaisesRegex(dev_build.SelectError, "no OS"):
            dev_build.select("workflow_dispatch", {"inputs": inputs})

    def test_non_boolean_input_fails(self) -> None:
        with self.assertRaises(dev_build.SelectError):
            dev_build.select("workflow_dispatch", {"inputs": {"linux": "yes"}})


class OutputTests(unittest.TestCase):
    def test_select_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = dev_build.select_outputs("pull_request", pr_event(["build:macos-x86_64"]), Path(tmp))
        self.assertEqual(out, {
            "build": "true", "linux": "false", "windows": "false", "macos": "true",
            "macos-archs": '["x86_64"]', "product": "CosmoSlice",
        })

    def test_skipped_event_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = dev_build.select_outputs("pull_request", pr_event([], action="labeled", label="bug"), Path(tmp))
        self.assertEqual((out["build"], out["linux"], out["macos-archs"]), ("false", "false", "[]"))

    def test_product_comes_from_the_packages_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            table = Path(tmp) / dev_build.PACKAGES_TABLE
            table.parent.mkdir(parents=True)
            table.write_text(json.dumps({"schema": 1, "product": "Other", "upstream": "OrcaSlicer"}), encoding="utf-8")
            self.assertEqual(dev_build.product(Path(tmp)), "Other")

    def test_cli_select_writes_github_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_path = Path(tmp) / "event.json"
            event_path.write_text(json.dumps({"inputs": {"linux": "true", "windows": "false",
                                                         "macos-arm64": "false", "macos-x86_64": "true"}}),
                                  encoding="utf-8")
            output = Path(tmp) / "out.txt"
            env = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_EVENT_PATH": str(event_path)}
            with mock.patch.dict(os.environ, env), redirect_stdout(io.StringIO()):
                self.assertEqual(dev_build.main(["select", "--output", str(output)]), 0)
            lines = output.read_text(encoding="utf-8").splitlines()
        self.assertIn("linux=true", lines)
        self.assertIn("windows=false", lines)
        self.assertIn('macos-archs=["x86_64"]', lines)

    def test_cli_reports_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            event_path = Path(tmp) / "event.json"
            event_path.write_text(json.dumps(pr_event(["build:freebsd"])), encoding="utf-8")
            env = {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": str(event_path)}
            err = io.StringIO()
            with mock.patch.dict(os.environ, env), redirect_stderr(err), redirect_stdout(io.StringIO()):
                self.assertEqual(dev_build.main(["select", "--output", str(Path(tmp) / "o")]), 1)
        self.assertIn("::error::", err.getvalue())


class VersionTests(unittest.TestCase):
    def tree(self, tmp: str, tool: str | None = None) -> Path:
        root = Path(tmp)
        (root / "version.inc").write_text('set(SoftFever_VERSION "2.5.2")\n', encoding="utf-8")
        if tool is not None:
            path = root / dev_build.COSMYX_VERSION
            path.parent.mkdir(parents=True)
            path.write_text(tool, encoding="utf-8")
        return root

    def test_upstream_names_without_the_cosmyx_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.tree(tmp)
            self.assertEqual(dev_build.version("pull_request", pr_event([], number=42), root), "PR-42")
            self.assertEqual(dev_build.version("workflow_dispatch", {}, root), "V2.5.2")

    def test_cosmyx_tool_names_the_build_with_the_pr_head(self) -> None:
        # A stand-in for cosmyx_version.py that echoes what it was asked.
        tool = ("import os, sys\n"
                "print('noise')\n"
                "print(sys.argv[-1] + ':' + os.environ.get('git_commit_hash', ''))\n")
        with tempfile.TemporaryDirectory() as tmp:
            root = self.tree(tmp, tool)
            self.assertEqual(dev_build.version("pull_request", pr_event([]), root), "build-tag:abcdef1234567890")
            self.assertEqual(dev_build.version("workflow_dispatch", {}, root), "build-tag:")

    def test_cosmyx_tool_failure_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = self.tree(tmp, "import sys\nsys.exit('broken')\n")
            with self.assertRaisesRegex(dev_build.SelectError, "broken"):
                dev_build.version("workflow_dispatch", {}, root)


class DmgPlanTests(unittest.TestCase):
    def plan(self, names: list[str]) -> dict[str, str]:
        return dev_build.dmg_plan(names, "arm64", "2.5.2-8_abc1234", "CosmoSlice", "f00d")

    def test_existing_product_dmg_is_kept(self) -> None:
        plan = self.plan(["CosmoSlice_Mac_arm64_2.5.2-8_abc1234", "OrcaSlicer_Mac_bundle_arm64_f00d"])
        self.assertEqual(plan["action"], "skip")

    def test_upstream_dmg_is_repacked(self) -> None:
        plan = self.plan(["OrcaSlicer_Mac_arm64_2.5.2-8_abc1234"])
        self.assertEqual(plan, {"action": "dmg", "source": "OrcaSlicer_Mac_arm64_2.5.2-8_abc1234",
                                "artifact": "CosmoSlice_Mac_arm64_2.5.2-8_abc1234"})

    def test_bundle_is_packed(self) -> None:
        plan = self.plan(["x", "OrcaSlicer_Mac_bundle_arm64_f00d", "OrcaSlicer_Mac_bundle_x86_64_f00d"])
        self.assertEqual(plan, {"action": "bundle", "source": "OrcaSlicer_Mac_bundle_arm64_f00d",
                                "artifact": "CosmoSlice_Mac_arm64_2.5.2-8_abc1234"})

    def test_product_dmg_under_another_version_is_kept(self) -> None:
        self.assertEqual(self.plan(["CosmoSlice_Mac_arm64_PR-3"])["action"], "skip")

    def test_other_arch_does_not_count(self) -> None:
        with self.assertRaises(dev_build.SelectError):
            self.plan(["CosmoSlice_Mac_x86_64_2.5.2-8_abc1234", "OrcaSlicer_Mac_bundle_x86_64_f00d"])

    def test_cli_reads_names_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            names = Path(tmp) / "names.txt"
            names.write_bytes(b"OrcaSlicer_Mac_bundle_arm64_f00d\r\n")
            output = Path(tmp) / "out.txt"
            argv = ["dmg-plan", "--arch", "arm64", "--ver", "V1", "--product", "CosmoSlice", "--sha", "f00d",
                    "--names-file", str(names), "--output", str(output)]
            with redirect_stdout(io.StringIO()):
                self.assertEqual(dev_build.main(argv), 0)
            self.assertIn("action=bundle", output.read_text(encoding="utf-8").splitlines())


class SealTests(unittest.TestCase):
    """The repacked app is sealed and verified before create_dmg: keep a
    signature that verifies, refuse a broken identity signature, re-seal
    anything else ad hoc, then always verify strictly."""

    def test_command_order_and_quoting(self) -> None:
        app = Path("stage dir") / "CosmoSlice.app"
        command = dev_build.seal_command(app)
        self.assertTrue(command.startswith(f"set -e; app={shlex.quote(str(app))}; "))
        steps = [command.index('codesign --verify --deep --strict "$app"'),
                 command.index("grep -q '^Authority='"),
                 command.index('codesign --force --deep --sign - "$app"'),
                 command.rindex('codesign --verify --deep --strict --verbose=2 "$app"')]
        self.assertEqual(steps, sorted(steps))
        self.assertTrue(command.endswith('codesign --verify --deep --strict --verbose=2 "$app"'))

    def test_cli_runs_the_command(self) -> None:
        commands: list[str] = []
        self.assertEqual(dev_build.main(["seal-app", "--app", "x y.app"], runner=commands.append), 0)
        self.assertEqual(commands, [dev_build.seal_command(Path("x y.app"))])

    def test_cli_failure_is_an_error(self) -> None:
        def fail(command: str) -> None:
            raise subprocess.CalledProcessError(1, command)
        with redirect_stderr(io.StringIO()) as err:
            self.assertEqual(dev_build.main(["seal-app", "--app", "a.app"], runner=fail), 1)
        self.assertIn("::error::", err.getvalue())


@unittest.skipUnless(shutil.which("codesign"), "codesign exists on macOS only")
class SealOnMacTests(unittest.TestCase):
    """A real bundle as upstream's unsigned build leaves it: the executable
    carries only its own ad-hoc (linker) signature and the bundle is not
    sealed, which `codesign --verify` rejects and Gatekeeper calls damaged."""

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
        exe = self.root / "OrcaSlicer"
        shutil.copyfile("/usr/bin/true", exe)
        subprocess.run(["codesign", "--remove-signature", str(exe)], check=True)
        subprocess.run(["codesign", "--force", "--sign", "-", "--identifier", "OrcaSlicer", str(exe)], check=True)
        exe.rename(app / "Contents" / "MacOS" / "OrcaSlicer")
        return app

    def verifies(self, app: Path) -> bool:
        return subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], capture_output=True).returncode == 0

    def test_repacked_app_is_sealed_and_verifies(self) -> None:
        # The job copies the app under the product name, then seals it.
        stage = self.root / "stage"
        stage.mkdir()
        app = stage / "CosmoSlice.app"
        subprocess.run(["cp", "-R", str(self.unsealed_app()), str(app)], check=True)
        self.assertFalse(self.verifies(app))  # the reported bug
        dev_build.run_bash(dev_build.seal_command(app))
        self.assertTrue(self.verifies(app))

    def test_valid_signature_is_kept(self) -> None:
        app = self.unsealed_app()
        subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
        seal = app / "Contents" / "_CodeSignature" / "CodeResources"
        before = seal.read_bytes()
        dev_build.run_bash(dev_build.seal_command(app))
        self.assertEqual(seal.read_bytes(), before)


def jobs(text: str) -> dict[str, str]:
    """Split the jobs: section into {job id: job body} on two-space keys."""
    section = text.split("\njobs:\n", 1)[1]
    parts = re.split(r"^  ([A-Za-z0-9_-]+):\n", section, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


def own_keys(body: str) -> dict[str, str]:
    """The job-level keys (four-space indent) of a job body."""
    return {key: value.strip() for key, value in re.findall(r"^    ([a-z-]+):(.*)$", body, flags=re.MULTILINE)}


def with_inputs(body: str) -> set[str]:
    """The input names a job passes under its `with:` block."""
    block = re.search(r"^    with:\n((?:      .*\n)+)", body, flags=re.MULTILINE)
    return set(re.findall(r"^      ([a-z-]+):", block.group(1), flags=re.MULTILINE)) if block else set()


def call_inputs(workflow: Path) -> set[str]:
    """The inputs a reusable workflow declares under on.workflow_call."""
    text = workflow.read_bytes().decode("utf-8").replace("\r\n", "\n")
    head = text.split("\njobs:\n", 1)[0]
    block = head.split("workflow_call:", 1)[1].split("inputs:", 1)[1]
    indent = min(len(m) for m in re.findall(r"^( +)[a-z-]+:", block, flags=re.MULTILINE))
    return set(re.findall(rf"^ {{{indent}}}([a-z-]+):", block, flags=re.MULTILINE))


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_bytes().decode("utf-8").replace("\r\n", "\n")
        self.jobs = jobs(self.text)

    def test_name_and_pull_request_trigger(self) -> None:
        self.assertIn("\nname: Cosmyx dev build\n", self.text)
        self.assertIn("    types: [opened, synchronize, reopened, labeled, unlabeled]\n", self.text)
        self.assertIn("    branches: ['cosmyx-ci/**']\n", self.text)

    def test_dispatch_checkboxes(self) -> None:
        dispatch = self.text.split("  workflow_dispatch:\n", 1)[1].split("\nconcurrency:", 1)[0]
        for name, default in dev_build.DISPATCH_DEFAULTS.items():
            with self.subTest(name=name):
                block = re.search(rf"^      {re.escape(name)}:\n((?:        .*\n)+)", dispatch, flags=re.MULTILINE)
                self.assertIsNotNone(block)
                self.assertIn("        type: boolean\n", block.group(1))
                self.assertIn(f"        default: {str(default).lower()}\n", block.group(1))

    def test_concurrency_per_pr_and_label_events_apart(self) -> None:
        block = self.text.split("\nconcurrency:\n", 1)[1].split("\njobs:\n", 1)[0]
        self.assertIn("github.event.pull_request.number || github.ref", block)
        self.assertIn("!startsWith(github.event.label.name, 'build:')", block)
        self.assertIn("github.run_id", block)
        self.assertIn("cancel-in-progress: true", block)

    def test_select_skips_non_build_label_events(self) -> None:
        keys = own_keys(self.jobs["select"])
        self.assertIn("startsWith(github.event.label.name, 'build:')", keys["if"])
        self.assertIn("workflow_dispatch", keys["if"])
        self.assertIn("dev_build.py select", self.jobs["select"])

    def test_builds_are_gated_by_the_selection(self) -> None:
        for job, output in (("build_linux", "linux"), ("build_windows", "windows"), ("build_macos_arch", "macos")):
            with self.subTest(job=job):
                keys = own_keys(self.jobs[job])
                self.assertEqual(keys["needs"], "select")
                self.assertIn(f"needs.select.outputs.{output} == 'true'", keys["if"])
                self.assertEqual(keys["uses"], "./.github/workflows/build_check_cache.yml")
                self.assertIn("secrets: inherit", self.jobs[job])
        self.assertIn("fromJSON(needs.select.outputs.macos-archs)", self.jobs["build_macos_arch"])

    def test_reusable_inputs_exist_in_the_called_workflow(self) -> None:
        for name, body in self.jobs.items():
            uses = own_keys(body).get("uses", "")
            if not uses.startswith("./.github/workflows/"):
                continue
            with self.subTest(job=name):
                declared = call_inputs(REPO_ROOT / uses[2:])
                self.assertLessEqual(with_inputs(body), declared)

    def test_unit_tests_follow_their_build(self) -> None:
        expected = {
            "unit_tests_linux_x86_64": "build_linux",
            "unit_tests_linux_aarch64": "build_linux",
            "unit_tests_windows_x64": "build_windows",
            "unit_tests_macos_arm64": "[select, build_macos_arch]",
        }
        for job, needs in expected.items():
            with self.subTest(job=job):
                keys = own_keys(self.jobs[job])
                self.assertEqual(keys["needs"], needs)
                self.assertEqual(keys["uses"], "./.github/workflows/unit_tests.yml")
                build = needs.strip("[]").split(", ")[-1]
                self.assertIn(f"needs.{build}.result == 'success'", keys["if"])

    def test_dmg_job_follows_the_mac_build(self) -> None:
        body = self.jobs["macos_dmg"]
        keys = own_keys(body)
        self.assertEqual(keys["needs"], "[select, build_macos_arch]")
        self.assertIn("needs.build_macos_arch.result == 'success'", keys["if"])
        self.assertIn("dev_build.py version", body)
        self.assertIn("dev_build.py dmg-plan", body)
        self.assertIn("create_dmg \"$PRODUCT\"", body)
        # The copied app is sealed and verified before it goes into the DMG.
        seal = body.index('dev_build.py seal-app --app "$stage/$PRODUCT.app"')
        self.assertLess(body.index('cp -R "$apps" "$stage/$PRODUCT.app"'), seal)
        self.assertLess(seal, body.index("create_dmg \"$PRODUCT\""))
        self.assertIn("name: ${{ steps.plan.outputs.artifact }}", body)

    def test_build_all_is_not_referenced(self) -> None:
        self.assertNotIn("build_all.yml\n", "\n".join(line for line in self.text.splitlines() if "uses:" in line))


if __name__ == "__main__":
    unittest.main()
