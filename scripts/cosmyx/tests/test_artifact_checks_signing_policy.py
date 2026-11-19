"""signing_policy: the 0098 truth table and the fork rule."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from artifact_checks import signing_policy as sp  # noqa: E402

ALL = {name: True for name in sp.SIGNING_SECRETS}
NONE = {name: False for name in sp.SIGNING_SECRETS}
OURS = "Cosmyx/OrcaSlicer"


class ModeTests(unittest.TestCase):
    def test_truth_table(self) -> None:
        cases = [
            # repository, event, branch, variables, secrets, expected
            (OURS, "workflow_dispatch", "DEV", {}, ALL, sp.ENFORCE),
            (OURS, "push", "release/2.6", {}, ALL, sp.ENFORCE),
            (OURS, "schedule", "DEV", {}, ALL, sp.ENFORCE),
            (OURS, "push", "DEV", {}, NONE, sp.NOT_CONFIGURED),
            (OURS, "push", "DEV", {}, {**ALL, "AZURE_CERT_PROFILE_NAME": False}, sp.NOT_CONFIGURED),
            (OURS, "pull_request", "DEV", {}, ALL, sp.REPORT),
            (OURS, "schedule", "MIXED", {"COSMYX_SIGN_ALL_REFS": "true"}, ALL, sp.REPORT),
            (OURS, "push", "feature/x", {}, ALL, sp.REPORT),
            (OURS, "push", "feature/x", {"COSMYX_SIGN_ALL_REFS": "true"}, ALL, sp.ENFORCE),
            (OURS, "push", "feature/x", {"COSMYX_SIGN_ALL_REFS": "TRUE"}, ALL, sp.REPORT),
            (OURS, "push", "feature/x", {"COSMYX_SIGN_ALL_REFS": "true"}, NONE, sp.NOT_CONFIGURED),
            ("OrcaSlicer/OrcaSlicer", "push", "release/2.6", {}, ALL, sp.REPORT),
            (OURS, "pull_request", "MIXED", {}, NONE, sp.REPORT),
        ]
        for repository, event, branch, variables, secrets, expected in cases:
            with self.subTest(repository=repository, event=event, branch=branch, variables=variables):
                self.assertEqual(sp.mode(repository, event, branch, variables, secrets), expected)

    def test_secrets_from_env_reads_only_flags(self) -> None:
        env = {f"COSMYX_HAS_{name}": "true" for name in sp.SIGNING_SECRETS}
        self.assertEqual(sp.missing_secrets(sp.secrets_from_env(env)), [])
        env["COSMYX_HAS_AZURE_TENANT_ID"] = "false"
        self.assertEqual(sp.missing_secrets(sp.secrets_from_env(env)), ["AZURE_TENANT_ID"])
        self.assertEqual(sp.missing_secrets(sp.secrets_from_env({})), list(sp.SIGNING_SECRETS))

    def test_mode_for_run(self) -> None:
        run = {"repository": {"full_name": OURS}, "event": "push", "head_branch": "DEV"}
        self.assertEqual(sp.mode_for_run(run, {}, ALL), sp.ENFORCE)
        run["head_branch"] = None
        self.assertEqual(sp.mode_for_run(run, {}, ALL), sp.REPORT)


class ExecTests(unittest.TestCase):
    def test_fork_builds_are_never_run(self) -> None:
        own = {"repository": {"full_name": OURS}, "head_repository": {"full_name": OURS}}
        fork = {"repository": {"full_name": OURS}, "head_repository": {"full_name": "someone/OrcaSlicer"}}
        unknown = {"repository": {"full_name": OURS}, "head_repository": None}
        self.assertTrue(sp.exec_ok(own))
        self.assertFalse(sp.exec_ok(fork))
        self.assertFalse(sp.exec_ok(unknown))


if __name__ == "__main__":
    unittest.main()
