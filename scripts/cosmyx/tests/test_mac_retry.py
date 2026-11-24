"""The macOS runner retry decides from the run's jobs and their annotations, and
its workflow keeps the trigger, permissions and concurrency it relies on
(decision 0217)."""

from __future__ import annotations

import importlib.util
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "cosmyx" / "ci" / "mac_retry.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cosmyx-mac-retry.yml"

_spec = importlib.util.spec_from_file_location("mac_retry", SCRIPT)
mac_retry = importlib.util.module_from_spec(_spec)
sys.modules["mac_retry"] = mac_retry
_spec.loader.exec_module(mac_retry)

REPO = "owner/repo"
RUN = 42
STARVED = "The job was not acquired by Runner of type hosted even after multiple attempts"


class FakeApi:
    """Answers the GitHub REST paths the script calls, records every call."""

    def __init__(self, jobs: list, annotations: dict | None = None, run: dict | None = None) -> None:
        self.jobs = jobs
        self.annotations = annotations or {}
        self.run = run or {"run_attempt": 1, "status": "completed"}
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, path: str) -> object:
        self.calls.append((method, path))
        page = int(re.search(r"[?&]page=(\d+)", path).group(1)) if "page=" in path else 1
        per_page = mac_retry.PER_PAGE
        if "/jobs?" in path:
            return {"jobs": self.jobs[(page - 1) * per_page:page * per_page]}
        match = re.search(r"/check-runs/(\d+)/annotations", path)
        if match:
            return [{"message": text} for text in self.annotations.get(int(match.group(1)), [])]
        if method == "POST":
            return None
        if path.endswith(f"/runs/{RUN}"):
            return self.run
        raise AssertionError(f"unexpected call {method} {path}")

    def posted(self) -> bool:
        return any(method == "POST" for method, _ in self.calls)


def job(job_id: int, name: str, conclusion: str) -> dict:
    return {"id": job_id, "name": name, "conclusion": conclusion}


def decide(api: FakeApi, attempt: int = 1, conclusion: str = "failure", max_attempts: int = 5):
    return mac_retry.decide(api, REPO, RUN, attempt, conclusion, max_attempts)


class DecideTests(unittest.TestCase):
    def test_cancelled_macos_job_without_runner_is_rerun(self) -> None:
        api = FakeApi(
            [job(1, "Build Linux", "success"), job(2, "build_macos_arch / Build macOS arm64", "cancelled")],
            {2: ["some warning", STARVED]},
        )
        decision = decide(api)
        self.assertTrue(decision.rerun)
        self.assertEqual(decision.jobs, ("build_macos_arch / Build macOS arm64",))

    def test_annotation_match_ignores_case(self) -> None:
        api = FakeApi([job(2, "MACOS arm64", "cancelled")], {2: [STARVED.upper()]})
        self.assertTrue(decide(api).rerun)

    def test_cancelled_macos_job_without_annotation_is_not_rerun(self) -> None:
        api = FakeApi([job(2, "Build macOS arm64", "cancelled")], {2: ["The operation was canceled."]})
        decision = decide(api)
        self.assertFalse(decision.rerun)
        self.assertIn("another cause", decision.reason)

    def test_attempt_at_the_limit_is_not_rerun(self) -> None:
        api = FakeApi([job(2, "Build macOS arm64", "cancelled")], {2: [STARVED]})
        for attempt in (5, 6):
            with self.subTest(attempt=attempt):
                self.assertFalse(decide(api, attempt=attempt).rerun)
        self.assertEqual(api.calls, [], "the limit is checked before any API call")

    def test_attempt_below_the_limit_is_rerun(self) -> None:
        api = FakeApi([job(2, "Build macOS arm64", "cancelled")], {2: [STARVED]})
        self.assertTrue(decide(api, attempt=4).rerun)

    def test_cancelled_non_macos_job_is_not_rerun(self) -> None:
        api = FakeApi([job(3, "Windows x64", "cancelled")], {3: [STARVED]})
        decision = decide(api)
        self.assertFalse(decision.rerun)
        self.assertIn("no cancelled or failed macOS job", decision.reason)

    def test_successful_run_is_not_rerun(self) -> None:
        api = FakeApi([job(2, "Build macOS arm64", "cancelled")], {2: [STARVED]})
        for conclusion in ("success", "skipped", "neutral"):
            with self.subTest(conclusion=conclusion):
                self.assertFalse(decide(api, conclusion=conclusion).rerun)
        self.assertEqual(api.calls, [])

    def test_cancelled_run_is_considered(self) -> None:
        api = FakeApi([job(2, "Build macOS arm64", "cancelled")], {2: [STARVED]})
        self.assertTrue(decide(api, conclusion="cancelled").rerun)

    def test_successful_macos_job_is_not_inspected(self) -> None:
        api = FakeApi([job(2, "Build macOS arm64", "success")], {2: [STARVED]})
        self.assertFalse(decide(api).rerun)
        self.assertFalse(any("annotations" in path for _, path in api.calls))

    def test_jobs_are_read_from_the_latest_attempt_on_every_page(self) -> None:
        filler = [job(100 + index, f"Linux {index}", "success") for index in range(mac_retry.PER_PAGE)]
        api = FakeApi(filler + [job(2, "Build macOS arm64", "cancelled")], {2: [STARVED]})
        self.assertTrue(decide(api).rerun)
        job_calls = [path for _, path in api.calls if "/jobs?" in path]
        self.assertEqual(len(job_calls), 2)
        self.assertTrue(all("filter=latest" in path for path in job_calls))


class RerunTests(unittest.TestCase):
    def test_unchanged_run_is_rerun(self) -> None:
        api = FakeApi([], run={"run_attempt": 2, "status": "completed"})
        done, _ = mac_retry.rerun(api, REPO, RUN, 2)
        self.assertTrue(done)
        self.assertIn(("POST", f"/repos/{REPO}/actions/runs/{RUN}/rerun-failed-jobs"), api.calls)

    def test_run_rerun_meanwhile_is_left_alone(self) -> None:
        api = FakeApi([], run={"run_attempt": 3, "status": "in_progress"})
        done, reason = mac_retry.rerun(api, REPO, RUN, 2)
        self.assertFalse(done)
        self.assertIn("attempt 3", reason)
        self.assertFalse(api.posted())

    def test_run_still_running_is_left_alone(self) -> None:
        api = FakeApi([], run={"run_attempt": 2, "status": "queued"})
        done, _ = mac_retry.rerun(api, REPO, RUN, 2)
        self.assertFalse(done)
        self.assertFalse(api.posted())


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        # Read as bytes: a CRLF checkout (Windows runner) must not change the text.
        self.text = WORKFLOW.read_bytes().decode("utf-8").replace("\r\n", "\n")

    def top_level(self, key: str) -> str:
        match = re.search(rf"^{key}:\n((?:[ #].*\n|\n)+)", self.text, flags=re.MULTILINE)
        self.assertIsNotNone(match, f"no top-level {key}:")
        return match.group(1)

    def test_triggered_by_completed_build_all_runs_only(self) -> None:
        on = self.top_level("on")
        self.assertRegex(on, r"^  workflow_run:\n", "workflow_run must be the only trigger")
        self.assertEqual(re.findall(r"^  (\w+):", on, flags=re.MULTILINE), ["workflow_run"])
        self.assertIn('workflows: ["Build all"]', on)
        self.assertIn("types: [completed]", on)

    def test_watched_workflow_name_exists(self) -> None:
        build_all = (REPO_ROOT / ".github" / "workflows" / "build_all.yml").read_text(encoding="utf-8")
        self.assertRegex(build_all, r"(?m)^name: Build all\s*$")

    def test_permissions_are_minimal(self) -> None:
        permissions = self.top_level("permissions")
        self.assertEqual(
            dict(re.findall(r"^  ([a-z-]+): (\w+)", permissions, flags=re.MULTILINE)),
            {"actions": "write", "checks": "read"},
        )

    def test_one_retry_per_commit_at_a_time(self) -> None:
        concurrency = self.top_level("concurrency")
        self.assertIn("group: cosmyx-mac-retry-${{ github.event.workflow_run.head_sha }}", concurrency)
        self.assertIn("cancel-in-progress: false", concurrency)

    def test_job_acts_only_on_failed_or_cancelled_runs(self) -> None:
        self.assertIn("github.event.workflow_run.conclusion == 'failure'", self.text)
        self.assertIn("github.event.workflow_run.conclusion == 'cancelled'", self.text)

    def test_steps_decide_wait_then_rerun(self) -> None:
        decide = self.text.index("mac_retry.py decide")
        wait = self.text.index('sleep "$MAC_RETRY_WAIT_SECONDS"')
        rerun = self.text.index("mac_retry.py rerun")
        self.assertLess(decide, wait)
        self.assertLess(wait, rerun)
        self.assertEqual(self.text.count("steps.decide.outputs.rerun == 'true'"), 2)

    def test_defaults(self) -> None:
        self.assertIn("vars.COSMYX_MAC_RETRY_MAX_ATTEMPTS || '5'", self.text)
        self.assertIn("vars.COSMYX_MAC_RETRY_WAIT_SECONDS || '900'", self.text)
        self.assertEqual(mac_retry.DEFAULT_MAX_ATTEMPTS, 5)


if __name__ == "__main__":
    unittest.main()
