"""Checks of the Cosmyx install and data folder wiring: the CPack overrides in
cmake/cosmyx/Packaging.cmake, the legacy-install removal snippet
cmake/cosmyx/remove_legacy_install.nsh and the one-line upstream hooks."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGING = REPO_ROOT / "cmake" / "cosmyx" / "Packaging.cmake"
LEGACY_NSH = REPO_ROOT / "cmake" / "cosmyx" / "remove_legacy_install.nsh"

UPSTREAM_REGISTRY_KEY = "OrcaSlicer"
UPSTREAM_VENDOR = "SoftFever"


def cmake_unquote(raw: str) -> str:
    """Value of a quoted CMake argument, escapes resolved once (as CMake parses it)."""
    return re.sub(r"\\(.)", r"\1", raw)


def top_level_sets(text: str) -> dict[str, str]:
    """Values of the unconditional and guarded set(VAR "value") calls of a CMake file."""
    values = {}
    for match in re.finditer(r'^\s*set\s*\(\s*(CPACK_[A-Z_]+)\s+"((?:[^"\\]|\\.)*)"\s*\)', text, flags=re.MULTILINE):
        values.setdefault(match.group(1), cmake_unquote(match.group(2)))
    return values


class PackagingValuesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = PACKAGING.read_text(encoding="utf-8")
        self.values = top_level_sets(self.text)

    def test_vendor_is_cosmyx(self) -> None:
        self.assertEqual(self.values["CPACK_PACKAGE_VENDOR"], "Cosmyx")

    def test_install_directory_is_nested_under_cosmyx(self) -> None:
        # Parsed twice: once by CMake here, once more from CPackConfig.cmake.
        once = self.values["CPACK_PACKAGE_INSTALL_DIRECTORY"]
        self.assertEqual(cmake_unquote(once), "Cosmyx\\CosmoSlice")

    def test_registry_key_never_matches_upstream(self) -> None:
        key = self.values["CPACK_PACKAGE_INSTALL_REGISTRY_KEY"]
        self.assertEqual(key, "Cosmyx CosmoSlice")
        self.assertNotEqual(key, UPSTREAM_REGISTRY_KEY)

    def test_display_and_package_names(self) -> None:
        for name in ("CPACK_NSIS_DISPLAY_NAME", "CPACK_NSIS_PACKAGE_NAME"):
            with self.subTest(name=name):
                self.assertEqual(self.values[name], "CosmoSlice")
                # Guarded, so a value set earlier (product-name branding) is kept.
                self.assertRegex(self.text, rf"if \(NOT DEFINED {name}\)\n\s+set\({name} ")

    def test_preinstall_commands_are_appended(self) -> None:
        self.assertIn('string(APPEND CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS "\\n${_cosmyx_legacy_include}")', self.text)
        # The only plain set() of the variable is the branch where it was empty.
        sets = re.findall(r"^\s*set\(CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS\b", self.text, flags=re.MULTILINE)
        self.assertEqual(len(sets), 1)
        self.assertRegex(self.text, r"if \(CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS\)\n\s+string\(APPEND")


@unittest.skipIf(shutil.which("cmake") is None, "cmake is not installed")
class PackagingScriptModeTests(unittest.TestCase):
    """Runs Packaging.cmake with cmake -P, as a Windows configure would see it."""

    def run_packaging(self, preinstall: str | None) -> dict[str, str]:
        with tempfile.TemporaryDirectory() as tmp:
            script = Path(tmp) / "probe.cmake"
            lines = ["set(WIN32 1)"]
            if preinstall is not None:
                lines.append(f'set(CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS "{preinstall}")')
            lines.append(f'include("{PACKAGING.as_posix()}")')
            for name in ("CPACK_PACKAGE_VENDOR", "CPACK_PACKAGE_INSTALL_REGISTRY_KEY",
                         "CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS"):
                lines.append(f'message("{name}=<${{{name}}}>")')
            script.write_text("\n".join(lines) + "\n", encoding="utf-8")
            result = subprocess.run(["cmake", "-P", str(script)], capture_output=True, text=True, check=True)
        return dict(re.findall(r"^(CPACK_[A-Z_]+)=<(.*?)>$", result.stderr, flags=re.MULTILINE | re.DOTALL))

    def test_signing_include_is_kept_first(self) -> None:
        values = self.run_packaging('!include \\\\\\"sign_windows.nsh\\\\\\"')
        lines = values["CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS"].split("\n")
        self.assertEqual(lines[0], '!include \\"sign_windows.nsh\\"')
        self.assertEqual(len(lines), 2)
        self.assertIn("remove_legacy_install.nsh", lines[1])

    def test_without_signing_only_the_legacy_include(self) -> None:
        values = self.run_packaging(None)
        commands = values["CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS"]
        self.assertTrue(commands.startswith('!include \\"'))
        self.assertTrue(commands.endswith('remove_legacy_install.nsh\\"'))
        self.assertEqual(values["CPACK_PACKAGE_VENDOR"], "Cosmyx")


class LegacyRemovalSnippetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw = LEGACY_NSH.read_bytes()
        self.text = self.raw.decode("utf-8")
        self.calls = re.findall(r'^!insertmacro CosmyxRemoveLegacyInstall (\S+) "([^"]+)" (\S+)$',
                                self.text, flags=re.MULTILINE)
        body = re.search(r"^!macro CosmyxRemoveLegacyInstall .*?^!macroend$", self.text,
                         flags=re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(body)
        self.macro = [line.strip() for line in body.group(0).splitlines()]

    def test_file_is_lf(self) -> None:
        self.assertNotIn(b"\r", self.raw)

    def test_publisher_matches_the_package_vendor(self) -> None:
        vendor = top_level_sets(PACKAGING.read_text(encoding="utf-8"))["CPACK_PACKAGE_VENDOR"]
        self.assertIn(f'!define COSMYX_LEGACY_PUBLISHER "{vendor}"', self.text)
        self.assertNotEqual(vendor, UPSTREAM_VENDOR)

    def test_never_targets_upstream_or_current_key(self) -> None:
        current = top_level_sets(PACKAGING.read_text(encoding="utf-8"))["CPACK_PACKAGE_INSTALL_REGISTRY_KEY"]
        self.assertTrue(self.calls)
        for hive, key, _ in self.calls:
            with self.subTest(key=key, hive=hive):
                self.assertIn(hive, ("HKLM", "HKCU"))
                self.assertNotEqual(key.lower(), UPSTREAM_REGISTRY_KEY.lower())
                self.assertNotEqual(key, current)
                self.assertTrue(key.startswith("Cosmyx "))

    def test_call_ids_are_unique(self) -> None:
        ids = [call_id for _, _, call_id in self.calls]
        self.assertEqual(len(ids), len(set(ids)))

    def test_publisher_check_guards_the_uninstaller(self) -> None:
        # The first test of the macro reads Publisher and skips unless it is exactly the
        # Cosmyx publisher; nothing runs or is deleted before that.
        read = self.macro.index('ReadRegStr $0 ${HIVE} "${COSMYX_UNINSTALL_ROOT}\\${KEY}" "Publisher"')
        check = self.macro.index('StrCmp $0 "${COSMYX_LEGACY_PUBLISHER}" 0 cosmyx_legacy_skip_${ID}')
        self.assertEqual(check, read + 1)
        destructive = [i for i, line in enumerate(self.macro)
                       if line.split(" ")[0] in ("ExecWait", "Exec", "Delete", "RMDir", "DeleteRegKey", "ExecShell")]
        self.assertTrue(destructive)
        self.assertGreater(min(destructive), check)
        self.assertNotIn("DeleteRegKey", " ".join(self.macro))
        self.assertFalse(any(line.startswith("RMDir /r") for line in self.macro))

    def test_skip_label_is_after_every_destructive_step(self) -> None:
        label = self.macro.index("cosmyx_legacy_skip_${ID}:")
        last = max(i for i, line in enumerate(self.macro) if line.split(" ")[0] in ("ExecWait", "Delete", "RMDir"))
        self.assertGreater(label, last)


class HookTests(unittest.TestCase):
    def test_cmake_hook_is_right_before_include_cpack(self) -> None:
        lines = (REPO_ROOT / "CMakeLists.txt").read_text(encoding="utf-8").splitlines()
        hook = "include(cmake/cosmyx/Packaging.cmake) # Cosmyx"
        self.assertEqual(lines.count(hook), 1)
        index = lines.index(hook)
        self.assertEqual(lines[index + 1], "include(CPack)")
        # Upstream's values are all set before the hook, so the overrides win.
        for name in ("CPACK_PACKAGE_VENDOR", "CPACK_PACKAGE_INSTALL_DIRECTORY",
                     "CPACK_PACKAGE_INSTALL_REGISTRY_KEY", "CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS"):
            with self.subTest(name=name):
                positions = [i for i, line in enumerate(lines) if re.match(rf"\s*set\s*\({name}\b", line)]
                self.assertTrue(positions)
                self.assertLess(max(positions), index)

    def test_cpp_hooks(self) -> None:
        expected = {
            "src/slic3r/GUI/GUI_App.cpp": [
                '#include "Cosmyx/AppPaths.hpp" // Cosmyx',
                "    Cosmyx::use_vendor_data_dir(); // Cosmyx",
                "    std::string legacy_data_dir_str = ::Slic3r::Cosmyx::without_vendor_dir(data_dir_path.string()); // Cosmyx",
                "    std::string default_path = xdg_config_dir(::Slic3r::Cosmyx::vendor_app_subdir(app_name.ToUTF8().data())); // Cosmyx",
            ],
            "src/libslic3r/utils.cpp": [
                '#include "Cosmyx/DataDir.hpp" // Cosmyx',
                "    return xdg_config_dir(Cosmyx::vendor_app_subdir(SLIC3R_APP_KEY)); // Cosmyx",
            ],
        }
        for path, hooks in expected.items():
            lines = (REPO_ROOT / path).read_text(encoding="utf-8").splitlines()
            for hook in hooks:
                with self.subTest(path=path, hook=hook):
                    self.assertEqual(lines.count(hook), 1)

    def test_vendor_call_follows_set_app_name(self) -> None:
        lines = (REPO_ROOT / "src/slic3r/GUI/GUI_App.cpp").read_text(encoding="utf-8").splitlines()
        index = lines.index("    Cosmyx::use_vendor_data_dir(); // Cosmyx")
        self.assertEqual(lines[index - 1], "    SetAppName(SLIC3R_APP_KEY);")


if __name__ == "__main__":
    unittest.main()
