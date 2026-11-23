"""Checks of the plugin package signature hooks (decision 0204): each upstream
hook line stays where the C++ relies on it, the test vectors are the CosmoCloud
file unchanged, and the empty production key table is flagged until a release
fills it."""

from __future__ import annotations

import json
import re
import unittest
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ("src", "slic3r", "plugin")
SIGNING_HEADER = REPO_ROOT / "src" / "slic3r" / "GUI" / "Cosmyx" / "logic" / "PluginSigning.hpp"
VECTORS = REPO_ROOT / "tests" / "cosmyx" / "data" / "plugin-signatures.json"


def read(*parts: str) -> list[str]:
    return REPO_ROOT.joinpath(*parts).read_text(encoding="utf-8").splitlines()


def cosmyx_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if "// Cosmyx" in line]


def index_of(lines: list[str], needle: str) -> int:
    found = [i for i, line in enumerate(lines) if needle in line]
    if len(found) != 1:
        raise AssertionError(f"{needle!r} found {len(found)} times")
    return found[0]


def production_keys(text: str) -> int:
    match = re.search(r"constexpr std::array<PinnedKey, (\d+)> PRODUCTION_KEYS", text)
    if match is None:
        raise AssertionError("PRODUCTION_KEYS table not found")
    return int(match.group(1))


class AgentHookTests(unittest.TestCase):
    def test_row_field(self) -> None:
        lines = read("src", "slic3r", "Utils", "OrcaCloudServiceAgent.hpp")
        start = lines.index("struct PluginDownloadData")
        field = index_of(lines, "nlohmann::json cosmyx_row; // Cosmyx")
        self.assertEqual(lines[field - 1].strip(), "std::string returned_os;")
        self.assertGreater(field, start)
        self.assertEqual(len(cosmyx_lines(lines)), 1)

    def test_row_is_kept_whole(self) -> None:
        lines = read("src", "slic3r", "Utils", "OrcaCloudServiceAgent.cpp")
        line = index_of(lines, "row.cosmyx_row    = item; // Cosmyx")
        self.assertIn('get_json_string_field(item, "returned_os")', lines[line - 1])


class CloudPluginServiceHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = read(*PLUGIN, "CloudPluginService.cpp")

    def test_include_follows_the_first_include(self) -> None:
        self.assertEqual(self.lines[0], '#include "CloudPluginService.hpp"')
        self.assertEqual(self.lines[1], '#include "slic3r/GUI/Cosmyx/PluginVerify.hpp" // Cosmyx')

    def test_verify_runs_after_the_empty_check_and_before_the_write(self) -> None:
        call = index_of(self.lines, "GUI::Cosmyx::verify_cloud_plugin_package(")
        empty = index_of(self.lines, 'error = _u8L("Plugin download returned empty data.");')
        sniff = index_of(self.lines, "const bool is_wheel   =")
        write = index_of(self.lines, "file.write(body.data(), body.size());")
        self.assertLess(empty, call)
        self.assertLess(call, sniff)
        self.assertLess(sniff, write)
        self.assertEqual(self.lines[call + 1].strip(), "return false; // Cosmyx")

    def test_the_chosen_row_is_kept(self) -> None:
        kept = index_of(self.lines, "cosmyx_item  = &item; // Cosmyx")
        self.assertEqual(self.lines[kept - 1].strip(), "download_url = item.download_link;")

    def test_hook_count(self) -> None:
        self.assertEqual(len(cosmyx_lines(self.lines)), 5)


class InstallHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lines = read(*PLUGIN, "PluginManager.cpp")
        self.function = index_of(self.lines, "bool PluginManager::install_cloud_plugin_package(")

    def test_include_follows_the_first_include(self) -> None:
        self.assertEqual(self.lines[1], '#include "slic3r/GUI/Cosmyx/PluginVerify.hpp" // Cosmyx')

    def test_scope_opens_before_the_install(self) -> None:
        # It reads the record of the package being replaced (the version floor)
        # before the installer moves it aside, and its destructor drops a
        # checked record that no install committed.
        scope = index_of(self.lines, "const GUI::Cosmyx::CloudInstallScope cosmyx_scope(descriptor); // Cosmyx")
        self.assertGreater(scope, self.function)
        self.assertEqual(self.lines[scope - 1].strip(), "error.clear();")

    def test_refused_commit_returns_before_the_entry_is_marked_installed(self) -> None:
        call = index_of(self.lines, "if (!cosmyx_scope.commit(installed, error)) { // Cosmyx")
        impl = [i for i in range(self.function, call) if "install_plugin_impl(package_path, installed" in self.lines[i]]
        self.assertEqual(len(impl), 1)
        self.assertEqual(self.lines[call - 1].strip(), "}")
        self.assertEqual(
            self.lines[call + 1].strip(),
            "if (failure != nullptr) *failure = CloudUpdateFailure::ReplacementInstalled; "
            "else set_plugin_error(plugin_key, error); // Cosmyx",
        )
        self.assertEqual(self.lines[call + 2].strip(), "return false; // Cosmyx")
        self.assertEqual(self.lines[call + 3].strip(), "} // Cosmyx")
        # Nothing of the upstream success path (descriptor marked installed and
        # enabled, error cleared) runs before the hook.
        marked = index_of(self.lines, "installed.cloud->installed        = true;")
        cleared = [i for i in range(call, len(self.lines)) if self.lines[i].strip() == "installed.clear_error();"]
        self.assertLess(call, marked)
        self.assertTrue(cleared)
        self.assertLess(call, cleared[0])

    def test_hook_count(self) -> None:
        self.assertEqual(len(cosmyx_lines(self.lines)), 6)

    def test_record_is_a_denied_filename(self) -> None:
        lines = read(*PLUGIN, "PluginAuditManager.cpp")
        denied = index_of(lines, '".cosmyx_package.json", // Cosmyx')
        self.assertEqual(lines[denied - 1].strip(), '".install_state.json",')
        self.assertIn('PACKAGE_RECORD_FILE = ".cosmyx_package.json"', SIGNING_HEADER.read_text(encoding="utf-8"))


class ImportNameHookTests(unittest.TestCase):
    def test_guard_after_the_entry_package_is_chosen(self) -> None:
        lines = read(*PLUGIN, "PluginFsUtils.cpp")
        self.assertEqual(lines[1], '#include "slic3r/GUI/Cosmyx/logic/PluginTrust.hpp" // Cosmyx')
        # The name rule only: upstream accepts a resource-only wheel here,
        # which holds no package at its top.
        guard = index_of(lines, "GUI::Cosmyx::check_entry_package_name(descriptor.entry_package, error)")
        self.assertIn("descriptor.entry_package = normalize_package_name(meta_name);", lines[guard - 2])
        self.assertEqual(lines[guard + 1].strip(), "return false; // Cosmyx")

    def test_guard_before_the_plugin_is_imported(self) -> None:
        # In PluginLoader, not in PythonInterpreter::load_module_from_whl():
        # upstream main drops that function, and the catalog can set the entry
        # package of a cloud plugin after the metadata check.
        lines = read(*PLUGIN, "PluginLoader.cpp")
        self.assertEqual(lines[1], '#include "slic3r/GUI/Cosmyx/logic/PluginTrust.hpp" // Cosmyx')
        guard = index_of(lines, "GUI::Cosmyx::check_entry_package(descriptor.entry_path, descriptor.entry_package, error)")
        self.assertIn("interpreter.load_module_from_file(descriptor.entry_path", lines[guard - 1])
        self.assertEqual(lines[guard - 2].strip(), "if (descriptor.entry_package.empty())")
        self.assertEqual(lines[guard + 1].strip(), "return nullptr; // Cosmyx")
        self.assertEqual(len(cosmyx_lines(lines)), 3)

    def test_interpreter_is_not_hooked(self) -> None:
        self.assertEqual(cosmyx_lines(read(*PLUGIN, "PythonInterpreter.cpp")), [])


class VectorsTests(unittest.TestCase):
    def test_vectors_are_the_cosmocloud_format(self) -> None:
        doc = json.loads(VECTORS.read_text(encoding="utf-8"))
        self.assertEqual(doc["format"], "cosmocloud-plugin-signature-vectors-v1")
        self.assertGreaterEqual(len(doc["rows"]), 85)
        reasons = {row["expect"] for row in doc["rows"]}
        self.assertEqual(
            reasons,
            {
                "ok", "malformed_row", "wrong_plugin", "wrong_version", "wrong_platform", "missing_signature",
                "unknown_key", "bad_signature", "size_mismatch", "sha256_mismatch", "kind_mismatch",
            },
        )

    def test_vector_keys_stay_out_of_the_production_table(self) -> None:
        doc = json.loads(VECTORS.read_text(encoding="utf-8"))
        header = SIGNING_HEADER.read_text(encoding="utf-8")
        for key in doc["keys"]:
            self.assertNotIn(key["public_key"], header)
            self.assertNotIn(key["key_id"], header)


class ProductionKeyTests(unittest.TestCase):
    def test_empty_table_is_flagged(self) -> None:
        # Warning level on purpose (decision 0204, like 0202): with no key every
        # install from the Cosmyx server is refused; a release must pin it.
        if production_keys(SIGNING_HEADER.read_text(encoding="utf-8")) == 0:
            warnings.warn(
                "PRODUCTION_KEYS is empty: plugins from the Cosmyx server cannot be installed; pin the key "
                "from `just plugin-keys` before a release (decision 0204).",
                stacklevel=1,
            )

    def test_table_parser(self) -> None:
        self.assertEqual(production_keys("constexpr std::array<PinnedKey, 2> PRODUCTION_KEYS{{...}};"), 2)
        with self.assertRaises(AssertionError):
            production_keys("nothing")


if __name__ == "__main__":
    unittest.main()
