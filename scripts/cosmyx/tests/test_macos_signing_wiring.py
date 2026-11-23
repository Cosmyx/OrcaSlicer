"""Checks of how macOS signing is wired into the CI: the "# Cosmyx" step of
build_orca.yml and the cosmyx-sign-macos action (decisions 0150, 0151, 0157).

GitHub cannot be run locally, so these read the YAML as text (standard library
only) and pin what a typo would silently break: the step's place, its gate,
the seven secret names, the secrets check, the cleanup and the pf token.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build_orca.yml"
ACTION = REPO_ROOT / ".github" / "actions" / "cosmyx-sign-macos" / "action.yml"

STEP = "Cosmyx sign and notarize macOS"
SECRETS = {
    "certificate-base64": "BUILD_CERTIFICATE_BASE64",
    "p12-password": "P12_PASSWORD",
    "keychain-password": "KEYCHAIN_PASSWORD",
    "certificate-id": "MACOS_CERTIFICATE_ID",
    "apple-id": "APPLE_DEV_ACCOUNT",
    "app-password": "APP_PWD",
    "team-id": "TEAM_ID",
}


def step_names(text: str) -> list[str]:
    return [m.group(1).split("#", 1)[0].strip() for m in re.finditer(r"^      - name: (.+)$", text, re.MULTILINE)]


def steps(text: str) -> list[tuple[str, list[str]]]:
    """Every step of the workflow as (name, lines), in file order."""
    found: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        match = re.match(r"^      - name: (.+)$", line)
        if match:
            found.append((match.group(1).split("#", 1)[0].strip(), [line]))
        elif found and (line.startswith("        ") or not line.strip()):
            found[-1][1].append(line)
        elif found and not line.startswith("      - "):
            found.append(("", []))  # a non-step line ends the current step
    return [step for step in found if step[0]]


def is_cosmyx_step(name: str, lines: list[str]) -> bool:
    """A step another Cosmyx task added: Cosmyx name, every line tagged."""
    return name.startswith("Cosmyx") and all(line.rstrip().endswith("# Cosmyx") for line in lines if line.strip())


def nearest_upstream_step_before(text: str, name: str) -> str:
    """The closest step before name that is not a Cosmyx-tagged step."""
    found = steps(text)
    position = [step[0] for step in found].index(name)
    for previous, lines in reversed(found[:position]):
        if not is_cosmyx_step(previous, lines):
            return previous
    return ""


def cosmyx_step(text: str, name: str) -> list[str]:
    """The lines of the "# Cosmyx" step called name (other tasks add their own)."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == f"- name: {name} # Cosmyx":
            body = [line]
            for following in lines[index + 1:]:
                if not following.rstrip().endswith("# Cosmyx"):
                    break
                body.append(following)
            return body
    return []


class WorkflowHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = WORKFLOW.read_text(encoding="utf-8")
        self.step = cosmyx_step(self.text, STEP)
        self.body = "\n".join(self.step)

    def test_step_present_once(self) -> None:
        self.assertTrue(self.step)
        self.assertEqual(step_names(self.text).count(STEP), 1)

    def test_step_sits_after_the_unsigned_dmg_and_before_the_uploads(self) -> None:
        names = step_names(self.text)
        position = names.index(STEP)
        # Other Cosmyx steps (the package renaming) may sit in between.
        self.assertEqual(nearest_upstream_step_before(self.text, STEP), "Create DMG without notary")
        self.assertEqual(names[position + 1], "Delete intermediate per-arch artifacts")
        self.assertLess(position, names.index("Upload artifacts mac"))

    def test_step_is_followed_by_a_blank_line(self) -> None:
        lines = self.text.splitlines()
        end = lines.index(self.step[-1])
        self.assertEqual(lines[end + 1], "")

    def test_gate(self) -> None:
        conditions = [line for line in self.step if line.strip().startswith("if:")]
        self.assertEqual(len(conditions), 1)
        for part in (
            "runner.os == 'macOS'",
            "inputs.macos-combine-only",
            "github.repository != 'OrcaSlicer/OrcaSlicer'",
            "github.event_name != 'pull_request'",
            "github.ref_name != 'MIXED'",
            "github.ref_name == 'DEV'",
            "startsWith(github.ref_name, 'release/')",
            "vars.COSMYX_SIGN_ALL_REFS == 'true'",
        ):
            self.assertIn(part, conditions[0])
        self.assertNotIn("secrets.", conditions[0])

    def test_step_passes_the_seven_secrets(self) -> None:
        self.assertIn("uses: ./.github/actions/cosmyx-sign-macos # Cosmyx", self.body)
        self.assertIn("timeout-minutes: 90 # Cosmyx", self.body)
        self.assertIn("version: ${{ env.ver }} # Cosmyx", self.body)
        self.assertIn("self-hosted: ${{ vars.SELF_HOSTED }} # Cosmyx", self.body)
        for name, secret in SECRETS.items():
            self.assertRegex(self.body, rf"\n\s+{re.escape(name)}: \$\{{\{{ secrets\.{secret} \}}\}} # Cosmyx")

    def test_every_line_is_tagged(self) -> None:
        self.assertEqual(len(self.step), 4 + 1 + 2 + len(SECRETS))

    def test_upstream_signing_stays_upstream_only(self) -> None:
        upstream = re.search(r"- name: Sign app and notary\n\s+if: (.+)", self.text)
        self.assertIsNotNone(upstream)
        self.assertIn("github.repository == 'OrcaSlicer/OrcaSlicer'", upstream.group(1))


class StepOrderRuleTests(unittest.TestCase):
    """Pins the order rule itself on synthetic workflows."""

    @staticmethod
    def workflow(between: str) -> str:
        return (
            "jobs:\n"
            "  build:\n"
            "    steps:\n"
            "      - name: Create DMG without notary\n"
            "        run: |\n"
            "          hdiutil create x.dmg\n"
            "\n"
            f"{between}"
            f"      - name: {STEP} # Cosmyx\n"
            "        uses: ./.github/actions/cosmyx-sign-macos # Cosmyx\n"
            "\n"
            "      - name: Delete intermediate per-arch artifacts\n"
            "        run: rm -rf x\n"
        )

    def test_direct_order_passes(self) -> None:
        self.assertEqual(nearest_upstream_step_before(self.workflow(""), STEP), "Create DMG without notary")

    def test_cosmyx_step_in_between_passes(self) -> None:
        between = (
            "      - name: Cosmyx package names mac-app # Cosmyx\n"
            "        uses: ./.github/actions/cosmyx-package-names # Cosmyx\n"
            "        with: # Cosmyx\n"
            "          stage: mac-app # Cosmyx\n"
            "\n"
        )
        self.assertEqual(nearest_upstream_step_before(self.workflow(between), STEP), "Create DMG without notary")

    def test_upstream_step_in_between_fails(self) -> None:
        between = "      - name: Upload artifacts mac\n        uses: actions/upload-artifact@v4\n\n"
        self.assertEqual(nearest_upstream_step_before(self.workflow(between), STEP), "Upload artifacts mac")

    def test_partly_tagged_cosmyx_step_in_between_fails(self) -> None:
        between = (
            "      - name: Cosmyx package names mac-app # Cosmyx\n"
            "        run: mv a b\n"
            "\n"
        )
        self.assertEqual(nearest_upstream_step_before(self.workflow(between), STEP), "Cosmyx package names mac-app")


class ActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = ACTION.read_text(encoding="utf-8")

    def test_inputs_reach_the_secrets_check(self) -> None:
        for name, secret in SECRETS.items():
            self.assertRegex(self.text, rf"\n  {re.escape(name)}:\n")
            self.assertIn(f"{secret}: ${{{{ inputs.{name} }}}}", self.text)
        names = re.search(r"names=\((.+)\)", self.text).group(1).split()
        self.assertEqual(sorted(names), sorted(SECRETS.values()))

    def test_none_partial_all(self) -> None:
        self.assertIn('echo "enabled=false" >> "$GITHUB_OUTPUT"', self.text)
        self.assertIn('echo "enabled=true" >> "$GITHUB_OUTPUT"', self.text)
        self.assertIn("::notice::macOS signing is off", self.text)
        self.assertIn("::error::macOS signing needs these secrets too", self.text)
        self.assertIn("value: ${{ steps.settings.outputs.enabled }}", self.text)

    def test_every_later_step_waits_for_the_settings(self) -> None:
        conditions = re.findall(r"^    - name: .+\n(?:      .+\n)*?      if: (.+)$", self.text, re.MULTILINE)
        steps = re.findall(r"^    - name: (.+)$", self.text, re.MULTILINE)
        self.assertEqual(len(conditions), len(steps) - 1)
        for condition in conditions:
            self.assertIn("steps.settings.outputs.enabled == 'true'", condition)

    def test_keychain(self) -> None:
        self.assertIn('keychain="$RUNNER_TEMP/cosmyx-signing.keychain-db"', self.text)
        self.assertIn('security set-keychain-settings -lut 21600 "$keychain"', self.text)
        self.assertIn('-A -t cert -f pkcs12 -k "$keychain"', self.text)
        self.assertIn("security set-key-partition-list -S apple-tool:,apple:,codesign: -s -k \"$KEYCHAIN_PASSWORD\"",
                      self.text)
        self.assertIn("cosmyx-keychains.txt", self.text)
        self.assertIn('"Developer ID Application: ', self.text)

    def test_pf_only_on_hosted_runners_and_released(self) -> None:
        self.assertIn("if: steps.settings.outputs.enabled == 'true' && inputs.self-hosted == ''", self.text)
        self.assertIn("sudo pfctl -E", self.text)
        self.assertIn('sudo pfctl -X "$(cat "$RUNNER_TEMP/cosmyx-pf-token.txt")"', self.text)

    def test_cleanup_always_runs(self) -> None:
        self.assertIn("if: always() && steps.settings.outputs.enabled == 'true'", self.text)
        self.assertIn('security delete-keychain "$keychain"', self.text)

    def test_runs_the_script_isolated_with_secrets_in_env(self) -> None:
        self.assertIn('python3 -I "$GITHUB_WORKSPACE/scripts/cosmyx/macos_signing/cli.py" run', self.text)
        for env, name in (("COSMYX_MAC_SIGN_IDENTITY", "certificate-id"), ("COSMYX_MAC_APPLE_ID", "apple-id"),
                          ("COSMYX_MAC_APP_PASSWORD", "app-password"), ("COSMYX_MAC_TEAM_ID", "team-id")):
            self.assertIn(f"{env}: ${{{{ inputs.{name} }}}}", self.text)

    def test_notary_log_artifact_on_failure(self) -> None:
        self.assertIn("if: failure() && steps.settings.outputs.enabled == 'true'", self.text)
        self.assertIn("name: cosmyx-notary-log-${{ inputs.version }}", self.text)

    def test_no_secret_is_echoed(self) -> None:
        for secret in SECRETS.values():
            self.assertNotRegex(self.text, rf"echo [^\n]*\${secret}")


if __name__ == "__main__":
    unittest.main()
