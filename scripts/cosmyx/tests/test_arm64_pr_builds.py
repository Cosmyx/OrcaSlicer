"""Integration builds run build_all.yml in pull request mode, through a draft
pull request based on a cosmyx-ci/<BASE> branch (decision 0216)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build_all.yml"
HOOK = "- 'cosmyx-ci/**'"

# The upstream triggers this hook must leave alone.
PUSH_BRANCHES = ["main", "release/*"]
UPSTREAM_PR_BRANCHES = ["main", "release/*"]


def triggers(text: str) -> dict[str, str]:
    """Split the on: section into {trigger: body} on two-space keys."""
    section = text.split("\non:\n", 1)[1]
    section = re.split(r"^\S", section, maxsplit=1, flags=re.MULTILINE)[0]
    parts = re.split(r"^  ([a-z_]+):[^\n]*\n", section, flags=re.MULTILINE)
    return dict(zip(parts[1::2], parts[2::2]))


def branches(body: str) -> list[str]:
    """The items of the branches: list of a trigger body, comments dropped."""
    match = re.search(r"^    branches:\n((?:     - .*\n)+)", body, flags=re.MULTILINE)
    if not match:
        return []
    items = [line.split(" #", 1)[0].strip()[2:].strip() for line in match.group(1).splitlines()]
    return [item.strip("'\"") for item in items]


class Arm64PullRequestBuildTests(unittest.TestCase):
    def setUp(self) -> None:
        # Read as bytes: upstream commits this file with CRLF line endings.
        self.text = WORKFLOW.read_bytes().decode("utf-8").replace("\r\n", "\n")
        self.triggers = triggers(self.text)

    def test_pull_requests_to_cosmyx_ci_branches_build(self) -> None:
        self.assertEqual(
            branches(self.triggers["pull_request"]),
            UPSTREAM_PR_BRANCHES + ["cosmyx-ci/**"],
        )

    def test_hook_is_one_tagged_line(self) -> None:
        lines = [line for line in self.text.splitlines() if "cosmyx-ci/" in line]
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].strip().startswith(HOOK), lines[0])
        self.assertIn("# Cosmyx:", lines[0])
        self.assertIn("0216", lines[0])

    def test_pull_request_paths_filter_still_applies(self) -> None:
        # An integration pull request changes src/**, so the filter lets it build.
        self.assertRegex(self.triggers["pull_request"], r"(?m)^    paths:\n(?:     - .*\n)*     - 'src/\*\*'")

    def test_push_and_manual_triggers_are_unchanged(self) -> None:
        self.assertEqual(branches(self.triggers["push"]), PUSH_BRANCHES)
        self.assertNotIn("cosmyx", self.triggers["push"].lower())
        self.assertIn("workflow_dispatch", self.triggers)
        self.assertNotIn("cosmyx", self.triggers["workflow_dispatch"].lower())
        self.assertIn("schedule", self.triggers)

    def test_pull_request_mode_builds_macos_arm64_only(self) -> None:
        # The point of the hook: upstream's pull request mode skips x86_64 and the
        # universal app. If upstream drops that, this decision needs a new look.
        self.assertIn(
            "github.event_name == 'pull_request' && '[\"arm64\"]'",
            self.text,
        )
        universal = self.text.split("\n  build_macos_universal:\n", 1)[1].split("\n  build_", 1)[0]
        self.assertIn("github.event_name != 'pull_request'", universal)


if __name__ == "__main__":
    unittest.main()
