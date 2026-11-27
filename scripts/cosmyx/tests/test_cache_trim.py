"""The MIXED cache trim selects only the large caches of refs/heads/MIXED, and
its workflow is gated to MIXED of this fork (decision 0227)."""

from __future__ import annotations

import importlib.util
import io
import re
import sys
import unittest
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "cosmyx" / "ci" / "cache_trim.py"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "cosmyx-cache-trim.yml"
BUILD_ALL = REPO_ROOT / ".github" / "workflows" / "build_all.yml"
CHECK_CACHE = REPO_ROOT / ".github" / "workflows" / "build_check_cache.yml"

_spec = importlib.util.spec_from_file_location("cache_trim", SCRIPT)
cache_trim = importlib.util.module_from_spec(_spec)
sys.modules["cache_trim"] = cache_trim
_spec.loader.exec_module(cache_trim)

MIXED = "refs/heads/MIXED"
MB = 1024 * 1024
REPO = "owner/repo"


def cache(key: str, size_mb: int, ref: str = MIXED, cache_id: int = 1) -> dict:
    return {"id": cache_id, "key": key, "ref": ref, "size_in_bytes": size_mb * MB}


# Shapes taken from the real cache listing of the fork.
LISTING = [
    cache("ccache-Flatpak-aarch64-45968697789-1", 1632, cache_id=1),
    cache("flatpak-builder-aarch64-a1543daa7a99", 1201, cache_id=2),
    cache("ccache-Windows-arm64-clang-45968697789-1", 892, cache_id=3),
    cache("ccache-macOS-x86_64-45968697789-1", 391, cache_id=4),
    cache("macos-15-arm64-cache-orcaslicer_deps-build-2449351d", 127, cache_id=5),
    cache("windows-x64-clang-cache-orcaslicer_deps-build-0416", 148, cache_id=6),
    cache("msys2-pkgs-upd:true-conf:9c8b69c4", 123, cache_id=7),
    cache("get-cmake-sha256-verified-v1-7aefad0c", 40, cache_id=8),
    cache("nsis-3.13", 1, cache_id=9),
    cache("macos-15-arm64-cache-orcaslicer_deps-build-1dbd5530", 127, "refs/pull/118/merge", 10),
    cache("ccache-Linux-amd64-1-1", 900, "refs/heads/DEV", 11),
]


class SelectTests(unittest.TestCase):
    def test_real_listing_keeps_the_deps_caches(self) -> None:
        self.assertEqual(cache_trim.select_keys(LISTING, MIXED), [
            "ccache-Flatpak-aarch64-45968697789-1",
            "flatpak-builder-aarch64-a1543daa7a99",
            "ccache-Windows-arm64-clang-45968697789-1",
            "ccache-macOS-x86_64-45968697789-1",
        ])

    def test_other_refs_are_never_selected(self) -> None:
        for ref in ("refs/heads/DEV", "refs/pull/118/merge", "MIXED", "refs/heads/mixed", ""):
            with self.subTest(ref=ref):
                self.assertEqual(cache_trim.select_keys(LISTING, ref), [])

    def test_entries_of_another_ref_in_a_mixed_listing_stay(self) -> None:
        keys = cache_trim.select_keys(LISTING, MIXED)
        self.assertNotIn("ccache-Linux-amd64-1-1", keys)

    def test_deps_caches_are_kept_whatever_their_size(self) -> None:
        # Build OrcaSlicer restores them with fail-on-cache-miss.
        listing = [cache("macos-15-universal-cache-orcaslicer_deps-build-abc", 2000)]
        self.assertEqual(cache_trim.select_keys(listing, MIXED, threshold_mb=1), [])

    def test_deps_key_pattern_matches_the_upstream_workflow(self) -> None:
        # Base-aware: skip on a base that builds the deps key elsewhere.
        if not CHECK_CACHE.is_file():
            self.skipTest("this upstream base has no build_check_cache.yml")
        keys = re.findall(r"echo cache-key=(.+?)\s*>>", CHECK_CACHE.read_text(encoding="utf-8"))
        if not keys:
            self.skipTest("this upstream base sets no deps cache-key in build_check_cache.yml")
        for key in keys:
            with self.subTest(key=key):
                self.assertIn(cache_trim.KEEP_MARKER, key)

    def test_prefix_selects_a_small_ccache(self) -> None:
        self.assertEqual(cache_trim.select_keys([cache("ccache-tiny", 1)], MIXED), ["ccache-tiny"])

    def test_threshold_is_inclusive(self) -> None:
        listing = [cache("big-deps", 256), cache("small-deps", 255)]
        self.assertEqual(cache_trim.select_keys(listing, MIXED), ["big-deps"])
        self.assertEqual(cache_trim.select_keys(listing, MIXED, threshold_mb=100), ["big-deps", "small-deps"])

    def test_prefix_match_is_case_sensitive_and_anchored(self) -> None:
        listing = [cache("CCACHE-x", 1), cache("deps-ccache-x", 1), cache("flatpak-x", 1)]
        self.assertEqual(cache_trim.select_keys(listing, MIXED), [])

    def test_malformed_entries_are_skipped(self) -> None:
        listing = [
            {"id": 1, "ref": MIXED, "size_in_bytes": 900 * MB},
            {"id": 2, "key": "", "ref": MIXED, "size_in_bytes": 900 * MB},
            {"id": 3, "key": 7, "ref": MIXED},
            {"id": 4, "key": "huge", "ref": MIXED, "size_in_bytes": "900000000"},
            {"id": 5, "key": "bool", "ref": MIXED, "size_in_bytes": True},
            {"id": 6, "key": "no-ref", "size_in_bytes": 900 * MB},
            {"id": 7, "key": "ccache-ok", "ref": MIXED},
        ]
        self.assertEqual(cache_trim.select_keys(listing, MIXED), ["ccache-ok"])

    def test_empty_listing(self) -> None:
        self.assertEqual(cache_trim.select_keys([], MIXED), [])


class FakeApi:
    def __init__(self, caches: list, statuses: list | None = None, missing: set | None = None) -> None:
        self.caches = list(caches)
        self.statuses = list(statuses or ["completed"])
        self.missing = missing or set()
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, path: str) -> object:
        self.calls.append((method, path))
        if method == "GET" and "/actions/caches?" in path:
            self.assertRef(path)
            page = int(re.search(r"[?&]page=(\d+)", path).group(1))
            per_page = cache_trim.PER_PAGE
            return {"actions_caches": self.caches[(page - 1) * per_page:page * per_page]}
        match = re.fullmatch(rf"/repos/{REPO}/actions/caches/(\d+)", path)
        if method == "DELETE" and match:
            cache_id = int(match.group(1))
            if cache_id in self.missing:
                raise urllib.error.HTTPError(path, 404, "Not Found", {}, io.BytesIO())
            self.caches = [item for item in self.caches if item["id"] != cache_id]
            return None
        if method == "GET" and path == f"/repos/{REPO}/actions/runs/42":
            status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            return {"status": status}
        raise AssertionError(f"unexpected call {method} {path}")

    @staticmethod
    def assertRef(path: str) -> None:
        assert "ref=refs%2Fheads%2FMIXED" in path, path

    def deleted(self) -> list[int]:
        return [int(path.rsplit("/", 1)[1]) for method, path in self.calls if method == "DELETE"]


class TrimTests(unittest.TestCase):
    def test_trim_deletes_only_the_selected_ids(self) -> None:
        api = FakeApi([item for item in LISTING if item["ref"] == MIXED])
        freed = cache_trim.trim(api, REPO, log=lambda _: None)
        self.assertEqual(api.deleted(), [1, 2, 3, 4])
        self.assertEqual(freed, (1632 + 1201 + 892 + 391) * MB)

    def test_trim_pages_through_the_listing(self) -> None:
        caches = [cache(f"ccache-{index}", 1, cache_id=index) for index in range(1, 151)]
        api = FakeApi(caches)
        cache_trim.trim(api, REPO, log=lambda _: None)
        self.assertEqual(len(api.deleted()), 150)

    def test_a_cache_gone_meanwhile_is_not_an_error(self) -> None:
        api = FakeApi([cache("ccache-a", 500, cache_id=1), cache("ccache-b", 500, cache_id=2)], missing={1})
        freed = cache_trim.trim(api, REPO, log=lambda _: None)
        self.assertEqual(freed, 500 * MB)

    def test_other_http_errors_fail_the_pass(self) -> None:
        class Forbidden(FakeApi):
            def __call__(self, method: str, path: str) -> object:
                if method == "DELETE":
                    raise urllib.error.HTTPError(path, 403, "Forbidden", {}, io.BytesIO())
                return super().__call__(method, path)

        with self.assertRaises(urllib.error.HTTPError):
            cache_trim.trim(Forbidden([cache("ccache-a", 1)]), REPO, log=lambda _: None)


class WatchTests(unittest.TestCase):
    def test_watch_trims_until_the_run_completes_then_once_more(self) -> None:
        api = FakeApi([cache("ccache-a", 500)], statuses=["in_progress", "in_progress", "completed"])
        sleeps: list[float] = []
        cache_trim.watch(api, REPO, 42, interval=7, sleep=sleeps.append, clock=lambda: 0.0, log=lambda _: None)
        self.assertEqual(sleeps, [7, 7])
        lists = [path for method, path in api.calls if "/actions/caches?" in path]
        self.assertEqual(len(lists), 3)

    def test_watch_stops_at_the_deadline(self) -> None:
        api = FakeApi([], statuses=["in_progress"])
        now = [0.0]

        def sleep(seconds: float) -> None:
            now[0] += seconds

        cache_trim.watch(api, REPO, 42, interval=60, deadline_minutes=5, sleep=sleep,
                         clock=lambda: now[0], log=lambda _: None)
        self.assertEqual(now[0], 300)

    def test_settings_must_be_positive_numbers(self) -> None:
        self.assertEqual(cache_trim.positive_int({}, "X", 9), 9)
        self.assertEqual(cache_trim.positive_int({"X": "12"}, "X", 9), 12)
        for bad in ("0", "-1", "abc", "1.5"):
            with self.subTest(value=bad), self.assertRaises(SystemExit):
                cache_trim.positive_int({"X": bad}, "X", 9)

    def test_usage(self) -> None:
        self.assertEqual(cache_trim.main(["cache_trim.py"]), 2)
        self.assertEqual(cache_trim.main(["cache_trim.py", "delete-all"]), 2)

    def test_the_trimmed_ref_is_mixed_only(self) -> None:
        self.assertEqual(cache_trim.TRIM_REF, MIXED)


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")

    def test_triggered_by_build_all_on_mixed_only(self) -> None:
        self.assertIn('    workflows: ["Build all"]\n', self.text)
        self.assertIn("    types: [requested, completed]\n", self.text)
        self.assertIn("    branches: [MIXED]\n", self.text)
        self.assertNotIn("pull_request", self.text)
        self.assertNotIn("schedule", self.text)

    def test_job_is_gated_to_the_fork_and_to_its_own_mixed(self) -> None:
        self.assertIn("github.repository != 'OrcaSlicer/OrcaSlicer'", self.text)
        self.assertIn("github.event.workflow_run.head_branch == 'MIXED'", self.text)
        self.assertIn("github.event.workflow_run.head_repository.full_name == github.repository", self.text)

    def test_permissions_are_actions_write_only(self) -> None:
        block = re.search(r"^permissions:\n((?:  .+\n)+)", self.text, flags=re.MULTILINE)
        self.assertIsNotNone(block)
        self.assertEqual(block.group(1), "  actions: write\n")

    def test_runs_this_script_with_no_third_party_action(self) -> None:
        self.assertIn("python3 scripts/cosmyx/ci/cache_trim.py", self.text)
        uses = re.findall(r"uses:\s*(\S+)", self.text)
        self.assertEqual([item.split("@")[0] for item in uses], ["actions/checkout"])

    def test_watch_fits_in_the_job_timeout(self) -> None:
        timeout = int(re.search(r"timeout-minutes: (\d+)", self.text).group(1))
        watch = int(re.search(r"CACHE_TRIM_WATCH_MINUTES: '(\d+)'", self.text).group(1))
        self.assertLess(watch, timeout)
        self.assertLessEqual(timeout, 360)

    def test_watched_workflow_name_matches_build_all(self) -> None:
        # Base-aware: an upstream base without build_all.yml has nothing to watch.
        if not BUILD_ALL.is_file():
            self.skipTest("this upstream base has no build_all.yml")
        name = re.search(r"^name:\s*['\"]?(.+?)['\"]?\s*$", BUILD_ALL.read_text(encoding="utf-8"), flags=re.MULTILINE)
        self.assertIsNotNone(name)
        self.assertEqual(name.group(1), "Build all")


if __name__ == "__main__":
    unittest.main()
