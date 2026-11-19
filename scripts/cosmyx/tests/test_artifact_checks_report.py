"""report: JUnit, Markdown, strict mode, broken jobs; and the cli resolve,
content and report commands end to end."""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import cli, report  # noqa: E402
from artifact_checks.records import Record, read_jsonl, write_jsonl  # noqa: E402

SHA = "aa9dac8f0123456789abcdef0123456789abcdef"
TAG = "2.6.0-dev-8_aa9dac8"


def sample() -> list[Record]:
    return [
        Record("windows", "a", "x.dll", "signature", "pass"),
        Record("windows", "a", "y.dll", "signature", "fail", "unsigned"),
        Record("linux", "b", "", "smoke", "skip", "aarch64", {"by_design": True}),
        Record("linux", "b", "", "translations", "skip", "T8 not merged"),
        Record("macos", "c", "OrcaSlicer.app", "bundle_sig", "warn", "not Developer-ID signed"),
    ]


class ReportTests(unittest.TestCase):
    def test_record_validation(self) -> None:
        with self.assertRaises(ValueError):
            Record("windows", "a", "", "nope", "pass")
        with self.assertRaises(ValueError):
            Record("windows", "a", "", "smoke", "ok")

    def test_junit(self) -> None:
        root = ET.fromstring(report.junit(sample(), strict=False).split("\n", 1)[1])
        self.assertEqual((root.get("tests"), root.get("failures"), root.get("skipped")), ("5", "1", "2"))
        names = [s.get("name") for s in root.iter("testsuite")]
        self.assertEqual(names, sorted(names))
        self.assertIn("windows.signature", names)

    def test_strict_fails_skips_not_by_design(self) -> None:
        records = sample()
        self.assertEqual([r.artifact for r in records if report.failing(r, True)], ["a", "b"])
        self.assertEqual(sum(report.failing(r, True) for r in records), 2)
        root = ET.fromstring(report.junit(records, strict=True).split("\n", 1)[1])
        self.assertEqual(root.get("failures"), "2")

    def test_markdown_caps_and_result(self) -> None:
        many = [Record("windows", "a", f"{i}.dll", "signature", "fail", "unsigned") for i in range(250)]
        text = report.markdown(many, "enforce", False)
        self.assertIn("Windows signing mode: **enforce**", text)
        self.assertIn("and 50 more", text)
        self.assertEqual(text.count("- **windows/signature**"), 200)
        self.assertIn("**Result: failed**", text)
        self.assertIn("nothing was checked", report.markdown([], "report", False))

    def test_markdown_escapes_untrusted_text(self) -> None:
        self.assertEqual(report.md_code("a``b"), "```a``b```")
        self.assertEqual(report.md_code("`x"), "`` `x ``")
        self.assertEqual(report.md_safe("a\nb\x1b"), "a\\x0ab\\x1b")
        self.assertEqual(report.md_cell("a|b"), "a\\|b")
        self.assertEqual(report.xml_safe("a\x01\ud800\tb"), "a\\x01\\ud800\tb")

    def test_job_records(self) -> None:
        records = [Record("windows", "a", "", "signature", "pass")]
        extra = report.job_records({"windows": "failure", "macos": "failure", "linux": "success"}, records)
        self.assertEqual([(r.os, r.status) for r in extra], [("macos", "fail")])

    def test_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(report.write(sample(), Path(tmp), "report", False))
            self.assertTrue(report.write(sample()[:1], Path(tmp), "report", False))
            self.assertTrue((Path(tmp) / "junit.xml").is_file())
            self.assertTrue((Path(tmp) / "report.md").read_text(encoding="utf-8").endswith("\n"))


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_cli(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = cli.main(list(args))
        return code, out.getvalue()

    def test_resolve(self) -> None:
        run = {"conclusion": "success", "event": "workflow_dispatch", "head_branch": "DEV", "head_sha": SHA,
               "html_url": "https://example.invalid/run", "repository": {"full_name": "Cosmyx/OrcaSlicer"},
               "head_repository": {"full_name": "Cosmyx/OrcaSlicer"}}
        names = [f"OrcaSlicer_Windows_{TAG}_x64_portable", f"OrcaSlicer_Mac_bundle_arm64_{SHA}",
                 f"OrcaSlicer_Linux_ubuntu_2404_{TAG}", f"{SHA}-tests-linux-x86_64"]
        (self.root / "run.json").write_text(json.dumps(run), encoding="utf-8")
        lines = [json.dumps({"id": i, "name": n, "expired": False}) for i, n in enumerate(names)]
        (self.root / "list.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        output = self.root / "github_output"
        code, _ = self.run_cli("resolve", "--run", str(self.root / "run.json"), "--artifacts-list",
                               str(self.root / "list.jsonl"), "--out", str(self.root / "out"),
                               "--github-output", str(output))
        self.assertEqual(code, 0)
        values = dict(line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
        self.assertEqual(values["skip"], "false")
        self.assertEqual(values["exec_ok"], "true")
        self.assertEqual(values["tag"], TAG)
        matrix = json.loads(values["matrix"])
        self.assertEqual([m["os"] for m in matrix], ["windows", "linux"])
        self.assertEqual(matrix[0]["runner"], "windows-latest")
        self.assertEqual(values["checked_oses"], "windows linux")
        self.assertIn(values["mode"], ("enforce", "not-configured"))
        records = {r.artifact: r.status for r in read_jsonl(self.root / "out" / "report-resolve.jsonl")}
        self.assertEqual(records["windows-installer x64"], "fail")
        self.assertEqual(records["mac-universal"], "fail")

    def test_resolve_skips_cancelled_runs(self) -> None:
        run = {"conclusion": "cancelled", "event": "push", "head_branch": "DEV", "head_sha": SHA,
               "repository": {"full_name": "Cosmyx/OrcaSlicer"}, "head_repository": None}
        outputs, _ = cli.resolve(run, [], {}, {}, False, cli.inventory.load_expectations())
        self.assertEqual((outputs["skip"], outputs["exec_ok"], outputs["matrix"]), ("true", "false", "[]"))

    def test_content_and_report(self) -> None:
        artifacts = self.root / "artifacts"
        (artifacts / f"OrcaSlicer_Linux_ubuntu_2404_{TAG}").mkdir(parents=True)
        code, _ = self.run_cli("content", "--os", "linux", "--tools", str(self.root), "--subject", str(self.root),
                               "--artifacts", str(artifacts), "--head-sha", SHA, "--out", str(self.root / "out"))
        self.assertEqual(code, 0)
        records = read_jsonl(self.root / "out" / "report-content-linux.jsonl")
        self.assertEqual([(r.check, r.status) for r in records], [("names", "skip")])
        summary = self.root / "summary.md"
        code, text = self.run_cli("report", "--in", str(self.root / "out"), "--out", str(self.root / "final"),
                                  "--mode", "report", "--strict", "false", "--job", "linux=success",
                                  "--step-summary", str(summary))
        self.assertEqual(code, 0)
        self.assertIn("**Result: passed**", text)
        self.assertEqual(summary.read_text(encoding="utf-8"),
                         (self.root / "final" / "report.md").read_text(encoding="utf-8"))
        code, _ = self.run_cli("report", "--in", str(self.root / "out"), "--out", str(self.root / "final"),
                               "--strict", "true")
        self.assertEqual(code, 1)
        write_jsonl(self.root / "out" / "report-linux.jsonl", [])
        code, _ = self.run_cli("report", "--in", str(self.root / "out"), "--out", str(self.root / "final"),
                               "--job", "windows=cancelled")
        self.assertEqual(code, 1)


REPO_ROOT = Path(__file__).resolve().parents[3]


class WorkflowTests(unittest.TestCase):
    """The workflow keeps its trust rules (decision 0141); checked as text, the
    standard library has no YAML parser."""

    def setUp(self) -> None:
        self.text = (REPO_ROOT / ".github" / "workflows" / "cosmyx-artifact-checks.yml").read_text(encoding="utf-8")

    def test_triggers_and_permissions(self) -> None:
        self.assertIn('workflows: ["Build all"]', self.text)
        self.assertIn("types: [completed]", self.text)
        self.assertIn("run_id:", self.text)
        self.assertIn("if: github.repository != 'OrcaSlicer/OrcaSlicer'", self.text)
        top = self.text.split("\njobs:", 1)[0]
        self.assertIn("permissions:\n  contents: read\n  actions: read\n", top)
        self.assertIn("cancel-in-progress: false", top)

    def test_checkouts_never_keep_credentials(self) -> None:
        self.assertEqual(self.text.count("uses: actions/checkout@"), self.text.count("persist-credentials: false"))

    def test_secrets_only_as_presence_flags(self) -> None:
        for line in self.text.splitlines():
            if "secrets." in line and not line.lstrip().startswith("#"):
                with self.subTest(line=line):
                    self.assertRegex(line, r"COSMYX_HAS_[A-Z_]+: \$\{\{ secrets\.[A-Z_]+ != '' \}\}$")
        for name in cli.signing_policy.SIGNING_SECRETS:
            with self.subTest(secret=name):
                self.assertIn(f"COSMYX_HAS_{name}: ${{{{ secrets.{name} != '' }}}}", self.text)

    def test_scripts_run_isolated_from_the_trusted_checkout(self) -> None:
        self.assertIn("CLI: tools/scripts/cosmyx/artifact_checks/cli.py", self.text)
        self.assertNotIn("python subject/", self.text)
        for line in self.text.splitlines():
            if line.strip().startswith("run: python") or line.strip().startswith("python "):
                with self.subTest(line=line):
                    self.assertIn("python -I", line)

    def test_commit_status_context(self) -> None:
        self.assertEqual(self.text.count("context=cosmyx/artifact-checks"), 2)

    def test_recipes(self) -> None:
        recipes = (REPO_ROOT / "scripts" / "cosmyx" / "just" / "tests.just").read_text(encoding="utf-8")
        lines = recipes.splitlines()
        for name in ("artifact-checks", "artifact-checks-status", "artifact-checks-local"):
            with self.subTest(recipe=name):
                index = next(i for i, line in enumerate(lines) if line.startswith(f"{name} ") or line.startswith(f"{name}:"))
                self.assertTrue(lines[index - 1].startswith("# "))


if __name__ == "__main__":
    unittest.main()
