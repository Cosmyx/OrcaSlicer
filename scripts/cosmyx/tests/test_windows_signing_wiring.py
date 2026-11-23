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


SETUP = "Cosmyx code signing setup"
SIGN = "Cosmyx sign Windows binaries"
VERIFY = "Cosmyx verify Windows signatures"
SIGNING_STEPS = (SETUP, SIGN, VERIFY)


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


def step_name(step: list[str]) -> str:
    return step[0].split("- name:", 1)[1].split("#", 1)[0].strip()


class WorkflowHookTests(unittest.TestCase):
    # Other tasks add their own "# Cosmyx" steps to build_orca.yml (sources
    # preparation, build naming, macOS signing), so the signing steps are
    # picked by name and only their own content and order are pinned.

    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.steps = cosmyx_steps(self.text)
        self.names = [step_name(step) for step in self.steps]
        self.by_name = {name: "\n".join(step) for name, step in zip(self.names, self.steps)}

    def test_signing_steps_present_once_and_in_order(self) -> None:
        for name in SIGNING_STEPS:
            self.assertEqual(self.names.count(name), 1, name)
        positions = [self.names.index(name) for name in SIGNING_STEPS]
        self.assertEqual(positions, sorted(positions))

    def test_only_the_setup_step_has_the_signing_id(self) -> None:
        owners = [name for name, body in self.by_name.items() if re.search(r"\n\s+id: cosmyx_sign # Cosmyx", body)]
        self.assertEqual(owners, [SETUP])

    def test_setup_passes_the_signing_secrets(self) -> None:
        setup = self.by_name[SETUP]
        self.assertIn("uses: ./.github/actions/cosmyx-sign # Cosmyx", setup)
        self.assertIn("mode: setup # Cosmyx", setup)
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
        conditions = [line for line in self.by_name[SETUP].splitlines() if line.strip().startswith("if:")]
        self.assertEqual(len(conditions), 1)
        for part in (
            "runner.os == 'Windows'",
            "github.repository != 'OrcaSlicer/OrcaSlicer'",
            "github.event_name != 'pull_request'",
            "github.ref_name != 'MIXED'",
            "github.ref_name == 'DEV'",
            "startsWith(github.ref_name, 'release/')",
        ):
            self.assertIn(part, conditions[0])

    def test_verify_requires_the_installer_where_one_is_built(self) -> None:
        # "Start installer Win" skips self-hosted runners, so only they may verify without one.
        self.assertIn("require-installer: ${{ !vars.SELF_HOSTED }} # Cosmyx", self.by_name[VERIFY])

    def test_sign_and_verify_follow_the_enabled_output(self) -> None:
        for name in (SIGN, VERIFY):
            self.assertIn("if: steps.cosmyx_sign.outputs.enabled == 'true' # Cosmyx", self.by_name[name])

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

    def verify_step(self) -> str:
        return self.text.split("- name: Verify Windows signatures", 1)[1]

    def test_verify_finds_the_installer_whatever_its_prefix(self) -> None:
        # The installer is renamed from OrcaSlicer_ to CosmoSlice_ on another branch: the lookup
        # goes through the script, which matches any prefix, never a hard-coded name.
        step = self.verify_step()
        self.assertIn("./scripts/cosmyx/find_windows_installer.ps1 @find", step)
        self.assertNotIn("OrcaSlicer_Windows_Installer", self.text)
        self.assertNotIn("CosmoSlice_Windows_Installer", self.text)
        script = (REPO_ROOT / "scripts" / "cosmyx" / "find_windows_installer.ps1").read_text(encoding="utf-8")
        self.assertIn("$Pattern = '*_Windows_Installer_*.exe'", script)

    def test_missing_installer_fails_unless_not_required(self) -> None:
        self.assertRegex(self.text, r"require-installer:\n\s+description: .*\n\s+required: false\n\s+default: 'true'")
        step = self.verify_step()
        self.assertIn("REQUIRE_INSTALLER: ${{ inputs.require-installer }}", step)
        self.assertIn("if ($env:REQUIRE_INSTALLER -ne 'true') { $find.Optional = $true }", step)

    def test_pins_reach_the_script(self) -> None:
        self.assertIn('"COSMYX_SIGN_SUBJECT=$env:SIGN_SUBJECT"', self.text)
        self.assertIn('"COSMYX_SIGN_EKU=$env:SIGN_EKU"', self.text)


if __name__ == "__main__":
    unittest.main()
