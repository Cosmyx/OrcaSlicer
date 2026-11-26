"""Checks of the CosmoCloud server hooks (decisions 0200 to 0203): the
upstream hook lines stay where the C++ relies on them, and the public key
placeholder is flagged until a release replaces it."""

from __future__ import annotations

import re
import unittest
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CLOUD_HEADER = REPO_ROOT / "src" / "slic3r" / "GUI" / "Cosmyx" / "logic" / "CloudServer.hpp"
PUB_KEY_PLACEHOLDER = "cosmocloud-public-key"


def read(*parts: str) -> list[str]:
    return REPO_ROOT.joinpath(*parts).read_text(encoding="utf-8").splitlines()


def cosmyx_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if "// Cosmyx" in line]


def pub_key(text: str) -> str:
    match = re.search(r'constexpr const char\* CLOUD_PUB_KEY = "([^"]*)";', text)
    if match is None:
        raise AssertionError("CLOUD_PUB_KEY constant not found")
    return match.group(1)


class StealthHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = read("src", "libslic3r", "AppConfig.cpp")

    def test_include_follows_the_own_header(self) -> None:
        # Not line 2: feat/cosmyx-dark-default puts its include there.
        index = self.lines.index('#include "AppConfig.hpp"')
        self.assertEqual(self.lines[index + 1], '#include "Cosmyx/StealthMode.hpp" // Cosmyx')

    def test_getter_returns_the_policy_first(self) -> None:
        index = self.lines.index("bool AppConfig::get_stealth_mode()")
        self.assertEqual(self.lines[index + 1], "{")
        self.assertTrue(self.lines[index + 2].startswith("    return Cosmyx::stealth_mode(*this); // Cosmyx"))

    def test_only_two_hook_lines(self) -> None:
        # Other Cosmyx features hook this file too, so count the stealth ones only.
        stealth = [line for line in cosmyx_lines(self.lines) if "StealthMode" in line or "stealth_mode" in line]
        self.assertEqual(len(stealth), 2)


class CloudServerHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = read("src", "slic3r", "GUI", "GUI_App.cpp")

    def test_include_is_present_once(self) -> None:
        include = '#include "Cosmyx/logic/CloudServer.hpp" // Cosmyx'
        self.assertEqual(self.lines.count(include), 1)

    def test_call_runs_right_before_the_agent_is_created(self) -> None:
        calls = [i for i, line in enumerate(self.lines) if "Cosmyx::apply_cloud_server(*app_config); // Cosmyx" in line]
        self.assertEqual(len(calls), 1)
        self.assertIn("Slic3r::create_agent_from_config(", self.lines[calls[0] + 1])

    def test_agent_is_created_in_one_place(self) -> None:
        creations = [line for line in self.lines if "create_agent_from_config(" in line]
        self.assertEqual(len(creations), 1)


class PreferencesHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = read("src", "slic3r", "GUI", "Preferences.cpp")

    def test_include_follows_the_first_include(self) -> None:
        self.assertEqual(self.lines[0], '#include "Preferences.hpp"')
        self.assertEqual(self.lines[1], '#include "Cosmyx/CloudServerPrefs.hpp" // Cosmyx')

    def test_panel_follows_the_network_test_row(self) -> None:
        calls = [i for i, line in enumerate(self.lines) if "Cosmyx::create_cloud_server_prefs(m_parent)" in line]
        self.assertEqual(len(calls), 1)
        self.assertTrue(self.lines[calls[0]].rstrip().endswith("(decision 0203)"))
        self.assertEqual(self.lines[calls[0] - 1].strip(), "g_sizer->Add(item_network_test);")

    def test_only_two_hook_lines(self) -> None:
        # Other Cosmyx features hook this file too, so count the cloud-server ones only.
        cloud = [line for line in cosmyx_lines(self.lines) if "CloudServer" in line or "cloud_server" in line]
        self.assertEqual(len(cloud), 2)


class PubKeyTests(unittest.TestCase):
    def test_key_is_one_constant(self) -> None:
        text = CLOUD_HEADER.read_text(encoding="utf-8")
        self.assertEqual(text.count("constexpr const char* CLOUD_PUB_KEY ="), 1)
        self.assertNotEqual(pub_key(text), "")

    def test_placeholder_is_flagged(self) -> None:
        # Warning level on purpose (decision 0202): development builds talk to a
        # CosmoCloud running with its default key; a release must replace it.
        if pub_key(CLOUD_HEADER.read_text(encoding="utf-8")) == PUB_KEY_PLACEHOLDER:
            warnings.warn(
                "CLOUD_PUB_KEY is still the CosmoCloud placeholder; replace it with the "
                "production key before a release (decision 0202).",
                stacklevel=1,
            )

    def test_key_parser_reads_the_constant(self) -> None:
        self.assertEqual(pub_key('constexpr const char* CLOUD_PUB_KEY = "abc";'), "abc")
        with self.assertRaises(AssertionError):
            pub_key("no key here")


if __name__ == "__main__":
    unittest.main()
