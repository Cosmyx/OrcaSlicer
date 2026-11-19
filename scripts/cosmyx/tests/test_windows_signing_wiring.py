"""Checks of how Windows signing is wired into the CI: the "# Cosmyx" steps of
build_orca.yml and the cosmyx-sign action (decisions 0093, 0095, 0098, 0099).

GitHub cannot be run locally, so these read the YAML as text (standard library
only) and pin the parts a typo would silently break: the secret names, the
gate on the action's `enabled` output, and the absence of a job environment.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build_orca.yml"
ACTION = REPO_ROOT / ".github" / "actions" / "cosmyx-sign" / "action.yml"

SECRETS = {
    "endpoint": "AZURE_TRUSTED_SIGNING_ENDPOINT",
    "account": "AZURE_CODE_SIGNING_NAME",
    "certificate-profile": "AZURE_CERT_PROFILE_NAME",
    "client-id": "AZURE_CLIENT_ID",
    "tenant-id": "AZURE_TENANT_ID",
    "subscription-id": "AZURE_SUBSCRIPTION_ID",
}


def cosmyx_steps(text: str) -> list[list[str]]:
    """Return the lines of each "# Cosmyx" step of the workflow, in order."""
    steps: list[list[str]] = []
    current: list[str] | None = None
    for line in text.splitlines():
        if line.rstrip().endswith("# Cosmyx"):
            if line.lstrip().startswith("- name:"):
                current = []
                steps.append(current)
            if current is not None:
                current.append(line)
        else:
            current = None
    return steps


class WorkflowHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.steps = cosmyx_steps(self.text)

    def test_three_cosmyx_steps(self) -> None:
        names = [step[0].split("- name:", 1)[1].split("#", 1)[0].strip() for step in self.steps]
        self.assertEqual(
            names,
            ["Cosmyx code signing setup", "Cosmyx sign Windows binaries", "Cosmyx verify Windows signatures"],
        )

    def test_setup_passes_the_signing_secrets(self) -> None:
        setup = "\n".join(self.steps[0])
        for name, secret in SECRETS.items():
            self.assertRegex(setup, rf"\n\s+{re.escape(name)}: \$\{{\{{ secrets\.{secret} \}}\}} # Cosmyx")
        self.assertIn("subject: ${{ vars.COSMYX_SIGN_SUBJECT }}", setup)
        self.assertIn("eku: ${{ vars.COSMYX_SIGN_EKU }}", setup)

    def test_no_secret_in_a_condition(self) -> None:
        # GitHub rejects the secrets context in a step's if:.
        for step in self.steps:
            for line in step:
                if line.strip().startswith("if:"):
                    self.assertNotIn("secrets.", line)

    def test_setup_condition_keeps_the_signed_refs(self) -> None:
        condition = next(line for line in self.steps[0] if line.strip().startswith("if:"))
        for part in (
            "runner.os == 'Windows'",
            "github.repository != 'OrcaSlicer/OrcaSlicer'",
            "github.event_name != 'pull_request'",
            "github.ref_name != 'MIXED'",
            "github.ref_name == 'DEV'",
            "startsWith(github.ref_name, 'release/')",
        ):
            self.assertIn(part, condition)

    def test_sign_and_verify_follow_the_enabled_output(self) -> None:
        for step in self.steps[1:]:
            self.assertIn("if: steps.cosmyx_sign.outputs.enabled == 'true' # Cosmyx", "\n".join(step))

    def test_no_job_environment(self) -> None:
        # Decision 0098: the OIDC subject is the ref, not an environment.
        self.assertIsNone(re.search(r"^    environment:", self.text, flags=re.MULTILINE))

    def test_no_repository_variables_for_the_settings(self) -> None:
        self.assertNotIn("vars.COSMYX_AZURE_", self.text)
        for name in ("COSMYX_SIGN_ENDPOINT", "COSMYX_SIGN_ACCOUNT", "COSMYX_SIGN_PROFILE"):
            self.assertNotIn(f"vars.{name}", self.text)


class ActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = ACTION.read_text(encoding="utf-8")

    def test_enabled_output_comes_from_the_settings_step(self) -> None:
        self.assertIn("value: ${{ steps.settings.outputs.enabled }}", self.text)
        self.assertIn("id: settings", self.text)

    def test_settings_step_checks_every_secret(self) -> None:
        for name, secret in SECRETS.items():
            self.assertIn(f"{secret}: ${{{{ inputs.{name} }}}}", self.text)
            self.assertIn(f"'{secret}'", self.text)

    def test_setup_work_waits_for_the_settings(self) -> None:
        guarded = re.findall(r"if: inputs\.mode == 'setup' && steps\.settings\.outputs\.enabled == 'true'", self.text)
        self.assertEqual(len(guarded), 2)
        self.assertNotRegex(self.text, r"if: inputs\.mode == 'setup'\s*\n")

    def test_pins_reach_the_script(self) -> None:
        self.assertIn('"COSMYX_SIGN_SUBJECT=$env:SIGN_SUBJECT"', self.text)
        self.assertIn('"COSMYX_SIGN_EKU=$env:SIGN_EKU"', self.text)


if __name__ == "__main__":
    unittest.main()
