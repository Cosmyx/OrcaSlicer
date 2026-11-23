# feat/cosmyx-install-paths (PR #106)

Analysed commits: `origin/DEV..origin/feat/cosmyx-install-paths`. Of its 14 commits, the first six (`6cbd27d0fc` to `39c40f609f`) are the shared foundation (T0, PR #86); the feature is the eight after it (`aa1a96c77e`, `3f6e3fa99d`, `bf1518a187`, `832f991e8e`, `66d55c84b8`, `cf37f3af00`, `7f51119c40`, `28aa25e538`).

## Purpose

A Cosmyx build must live side by side with an upstream OrcaSlicer install without sharing presets, sign-in, plugins, or installer entries (task T17, decisions 0180 to 0185, `wiki/cosmyx/install-and-data-paths.md`).

- User data folder: always under a `Cosmyx` vendor folder: `%APPDATA%\Cosmyx\OrcaSlicer`, `~/Library/Application Support/Cosmyx/OrcaSlicer`, `$XDG_CONFIG_HOME/Cosmyx/OrcaSlicer` (default `~/.config/Cosmyx/OrcaSlicer`). The inner name stays `SLIC3R_APP_KEY` (`OrcaSlicer`). A portable `data_dir` next to the executable and `--datadir` still override. Nothing is migrated, not even upstream's legacy Flatpak data (**Breaking** for users coming from the un-nested folder).
- Windows installer: installs to `Program Files\Cosmyx\CosmoSlice`, uninstall key `Cosmyx CosmoSlice`, publisher `Cosmyx`, display name `CosmoSlice`, Start menu folder `Cosmyx\CosmoSlice`. It silently removes an earlier CosmoSlice build (key `Cosmyx OrcaSlicer`, publisher `Cosmyx`) only when that publisher matches; upstream's key `OrcaSlicer` is never touched.

## Parent and dependencies

- Parent: `DEV`. No dependency on other feature branches; depends on the foundation (T0, PR #86) carried in the branch.
- Interaction with the product-name branding (decision 0132, `cosmyx-src/branding/product-name/`, other branch): the branding appends `CPACK_NSIS_DISPLAY_NAME "CosmoSlice"` at build time and owns the Start menu shortcut label (`CPACK_PACKAGE_EXECUTABLES`) and the executable name; `Packaging.cmake` guards its own display name with `if (NOT DEFINED ...)` so both agree.
- Interaction with Windows signing (PR #96): `Packaging.cmake` appends its legacy-removal include to `CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS` after upstream's signing include and never replaces it.
- Upstream APIs used: `xdg_config_dir()` and `default_data_dir()` (`libslic3r/utils.cpp`, Linux), `SLIC3R_APP_KEY`, `wxApp::SetVendorName`, `wxStandardPaths::UseAppInfo(AppInfo_VendorName | AppInfo_AppName)`, `GUI_App::init_app_config()`, `migrate_flatpak_legacy_datadir()`, `check_old_linux_datadir()`, top-level CPack variables `CPACK_PACKAGE_VENDOR`, `CPACK_PACKAGE_INSTALL_DIRECTORY`, `CPACK_PACKAGE_INSTALL_REGISTRY_KEY`, `CPACK_NSIS_DISPLAY_NAME`, `CPACK_NSIS_PACKAGE_NAME`, `CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS`, `CPACK_NSIS_ENABLE_UNINSTALL_BEFORE_INSTALL`.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `src/libslic3r/Cosmyx/DataDir.hpp`, `.cpp` | Cosmyx-owned | `DATA_DIR_VENDOR = "Cosmyx"`; `vendor_app_subdir(app_key)` returns `Cosmyx/<app_key>` with the native separator; `skip_legacy_data_migration(data_dir)` is true when the data folder sits right under a `Cosmyx` folder (trailing separators ignored). |
| `src/slic3r/GUI/Cosmyx/AppPaths.hpp`, `.cpp` | Cosmyx-owned | `use_vendor_data_dir()`: `SetVendorName("Cosmyx")` then `wxStandardPaths::Get().UseAppInfo(vendor | app name)`. Does nothing without a wxApp. Also moves `GetUserDataDir()` on Linux to `~/.Cosmyx/OrcaSlicer`. |
| `src/libslic3r/utils.cpp` | upstream hook | Line 2: `#include "Cosmyx/DataDir.hpp" // Cosmyx` (after `#include "Utils.hpp"`). Last line of `default_data_dir()` (Linux, after the portable `data_dir` check): `return xdg_config_dir(SLIC3R_APP_KEY);` becomes `return xdg_config_dir(Cosmyx::vendor_app_subdir(SLIC3R_APP_KEY)); // Cosmyx`. |
| `src/slic3r/GUI/GUI_App.cpp` | upstream hook | (a) after `#include "Downloader.hpp"` (last quoted include of the first block): `#include "Cosmyx/AppPaths.hpp" // Cosmyx`. (b) in `init_app_config()` right after `SetAppName(SLIC3R_APP_KEY);`: `Cosmyx::use_vendor_data_dir(); // Cosmyx` (the commented `SetAppDisplayName` lines below stay untouched; branding patches that exact line). (c) in `static void migrate_flatpak_legacy_datadir(...)`, right after the "Not running as a Flatpak, nothing to migrate." return: `if (::Slic3r::Cosmyx::skip_legacy_data_migration(data_dir_path.string())) return; // Cosmyx: start fresh (decision 0184)`. (d) in `check_old_linux_datadir()`: `std::string default_path = xdg_config_dir(app_name.ToUTF8().data());` becomes `std::string default_path = xdg_config_dir(::Slic3r::Cosmyx::vendor_app_subdir(app_name.ToUTF8().data())); // Cosmyx`. Libslic3r helpers are called fully qualified because inside `Slic3r::GUI` the name `Cosmyx` finds `Slic3r::GUI::Cosmyx` first. |
| `tests/libslic3r/test_utils.cpp` | upstream hook (test) | Include `#include "libslic3r/Cosmyx/DataDir.hpp" // Cosmyx` after `#include "libslic3r/Utils.hpp"`. In `TEST_CASE("default_data_dir is the XDG config dir without a portable data_dir folder", "[utils]")` (Linux only), `CHECK(Slic3r::default_data_dir() == "/tmp/xdg-test/" SLIC3R_APP_KEY);` becomes `CHECK(Slic3r::default_data_dir() == "/tmp/xdg-test/" + Slic3r::Cosmyx::vendor_app_subdir(SLIC3R_APP_KEY)); // Cosmyx` (decision 0185). |
| `CMakeLists.txt` (top level) | upstream hook | `include(cmake/cosmyx/Packaging.cmake) # Cosmyx` between `set(CPACK_GENERATOR NSIS)` and `include(CPack)` (after every upstream `CPACK_*` value). |
| `cmake/cosmyx/Packaging.cmake` | Cosmyx-owned | Overrides `CPACK_PACKAGE_VENDOR` (`Cosmyx`), `CPACK_PACKAGE_INSTALL_DIRECTORY` (`Cosmyx\\\\CosmoSlice`, backslashes doubled twice like upstream's icon path), `CPACK_PACKAGE_INSTALL_REGISTRY_KEY` (`Cosmyx CosmoSlice`), defaults `CPACK_NSIS_DISPLAY_NAME` and `CPACK_NSIS_PACKAGE_NAME` to `CosmoSlice` when undefined, and on WIN32 appends `!include` of the legacy removal snippet to `CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS`. |
| `cmake/cosmyx/remove_legacy_install.nsh` | Cosmyx-owned | NSIS macro `CosmyxRemoveLegacyInstall HIVE KEY ID`: for key `Cosmyx OrcaSlicer` in HKLM and HKCU, only when `Publisher` is exactly `Cosmyx`, runs the registered uninstaller silently (`/S _?=<dir>`), then deletes it and the folder if empty. |
| `tests/cosmyx/test_cosmyx_paths.cpp` | test | Catch2, see Verification. |
| `scripts/cosmyx/tests/test_install_paths.py` | test | unittest, see Verification. |
| `wiki/cosmyx/install-and-data-paths.md`, `wiki/decisions/0180` to `0185` | docs | Paths per OS, fresh start, installer identity, legacy removal, no migration, test hook. |
| `CHANGELOG.md` | docs | T17 line (repo area, under `<!-- cosmyx-slot: T17 -->`) flagged **Breaking:**; says "Pull request: pending". Also the T17 slot marker. |

Foundation (shared): the five hooks listed in decision 0002 (`src/libslic3r/CMakeLists.txt`, `src/slic3r/CMakeLists.txt`, `tests/CMakeLists.txt`, `PrintConfig.cpp`, `GCode.cpp`), the Cosmyx modules, `cosmyx_tests`, `justfile`, `cosmyx-checks.yml`, `scripts/cosmyx/{decisions.py,run_script_tests.py}`, decisions 0001 to 0005, `wiki/decisions/README.md`.

## Rebase risk zones

| Upstream file / function | v2.5.1 vs DEV | Churn 2026 |
|--------------------------|---------------|-----------|
| `src/libslic3r/utils.cpp`, `default_data_dir()` | Same function, same last line (`return xdg_config_dir(SLIC3R_APP_KEY);`, line 411 on the tag) after the portable `data_dir` check. The tag lacks `is_running_in_flatpak()` and `wayland_socket_available()` (46 lines deleted vs DEV), unrelated to the hook. | 31 |
| `tests/libslic3r/test_utils.cpp` | The `default_data_dir` test exists on the tag (line 588 to 590) with the same expected value. 1 insertion, 79 deletions elsewhere. | 12 |
| `src/slic3r/GUI/GUI_App.cpp` | `#include "Downloader.hpp"` (line 28), `SetAppName(SLIC3R_APP_KEY);` (line 2744), `check_old_linux_datadir()` default path line (637) and `migrate_flatpak_legacy_datadir()` (line 594) all exist. Difference in the migration function: on the tag the guard is `if(!boost::filesystem::exists("/.flatpak-info")) return; // Not running as a Flatpak, nothing to migrate.`, on DEV it is `if (!is_running_in_flatpak()) return; // ...`. The hook is a pure insertion after that `return;` line, so it applies with either, but a patch whose context contains the `if` line will not. | 246 |
| `CMakeLists.txt` | `include(CPack)` at line 1411 on the tag, preceded by `set(CPACK_GENERATOR NSIS)` and `set(CPACK_WIX_UPGRADE_GUID ...)`; upstream's signing block that sets `CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS` (`if (WIN32 AND DEFINED ENV{ORCA_SIGN_KMS_KEY})`) is also on the tag. `CPACK_PACKAGE_VENDOR "SoftFever"` (line 1350), `CPACK_PACKAGE_INSTALL_DIRECTORY ${CPACK_PACKAGE_NAME}` (1367), `CPACK_PACKAGE_INSTALL_REGISTRY_KEY "OrcaSlicer"` (1374), `CPACK_NSIS_ENABLE_UNINSTALL_BEFORE_INSTALL ON` (1375) all present. 12 insertions, 38 deletions elsewhere. | 73 |
| `src/libslic3r/CMakeLists.txt`, `src/slic3r/CMakeLists.txt`, `tests/CMakeLists.txt`, `PrintConfig.cpp`, `GCode.cpp` (foundation hooks) | All anchors present on the tag. | 127, 205, 9, 385, 342 |

Other upstream facts the feature depends on: on Windows and macOS the data folder comes from `wxStandardPaths::GetUserDataDir()` (no upstream legacy copy there); the only upstream legacy copy is the Flatpak one. Check on each base: `git grep -n "migrate\|legacy" -- src/slic3r/GUI/GUI_App.cpp` for any new data-folder migration that would copy upstream data into `Cosmyx/OrcaSlicer`.

## Intent to preserve

- Data folder is `<config root>/Cosmyx/OrcaSlicer` on every OS, never shared with upstream; the portable `data_dir` and `--datadir` keep upstream behaviour (not nested).
- Nothing is copied from the un-nested or Flatpak-legacy folders into the Cosmyx folder.
- The Windows installer identity is `Cosmyx` / `Cosmyx CosmoSlice` / `Program Files\Cosmyx\CosmoSlice`; it never removes an install whose key is `OrcaSlicer` or whose publisher is not exactly `Cosmyx`; it never replaces upstream's signing include.

If upstream rewrote the hooked code: if `default_data_dir()` or `xdg_config_dir()` change, keep the nesting by applying `vendor_app_subdir()` at whatever single point computes the default Linux config directory. If upstream adds another default-path computation or migration (for example for Windows or macOS), route it through `Cosmyx::vendor_app_subdir` / `skip_legacy_data_migration` rather than patching its internals more than one line. If the CPack block moves or is split, keep `Packaging.cmake` included after all upstream `CPACK_*` assignments and before `include(CPack)`; never edit upstream's `CPACK_*` lines. If upstream changes the NSIS signing include to something other than appending to `CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS`, keep appending ours (never `set`). If the upstream test is rewritten, keep an expectation that goes through `vendor_app_subdir()` (decision 0185).

## Verification

Catch2 (`tests/cosmyx/test_cosmyx_paths.cpp`, `[cosmyx][CosmyxPaths]`): "The data folder vendor is Cosmyx and the folder keeps the upstream name", "The Cosmyx data folder is never the target of a legacy data migration", "The XDG data folder is nested under Cosmyx", "default_data_dir() on Linux is the nested XDG folder". Upstream suite `[utils]` on Linux: "default_data_dir is the XDG config dir without a portable data_dir folder" (hooked test), run with `ctest --test-dir build -C Release -R "utils|cosmyx"`. Foundation Catch2 cases as in the version branch.

Script tests (`just test-scripts`, `scripts/cosmyx/tests/test_install_paths.py`): `PackagingValuesTests` (vendor, install directory, registry key never equals upstream, names, pre-install commands appended), `PackagingScriptModeTests` (runs `Packaging.cmake` with `cmake -P` when cmake is installed; signing include kept first; only the legacy include without signing), `LegacyRemovalSnippetTests` (LF, publisher equals the package vendor, never targets upstream or current key, unique call ids, publisher check guards the uninstaller, skip label after every destructive step), `HookTests` (CMake hook right before `include(CPack)`, C++ hooks, Flatpak skip first after the Flatpak check, vendor call follows `SetAppName`).

Manual after rebase: on Linux `XDG_CONFIG_HOME=/tmp/x orca-slicer` creates `/tmp/x/Cosmyx/OrcaSlicer`; on Windows the NSIS installer built by CI installs under `Program Files\Cosmyx\CosmoSlice` with Apps & features showing publisher `Cosmyx`; an upstream OrcaSlicer install stays intact.

## Known pitfalls

- `cf37f3af00` / `66d55c84b8`: the first Flatpak hook rewrote the legacy path without the vendor folder, so a Cosmyx Flatpak copied upstream's `io.github.softfever.OrcaSlicer` data into `Cosmyx/OrcaSlicer`. Replaced by the one-line early return plus the predicate (decision 0184); the upstream path line is back to upstream's text.
- `7f51119c40`: on the Windows runner, `core.autocrlf` made the NSIS snippet CRLF; macro regexes with `^...$` never matched and six tests failed in `setUp`. Tests fold CRLF to LF and read the committed blob with `git cat-file` for the LF check.
- `28aa25e538`: upstream's Linux-only `default_data_dir` test failed on every Cosmyx build after the move; fixed with a two-line tagged hook (an explicit exception to "no edits to upstream tests", decision 0185).
- Include placement: lines 2 to 4 of `GUI_App.cpp` are taken by other branches, so the include goes after `Downloader.hpp` (decision 0181).
- CMake backslashes: `CPACK_PACKAGE_INSTALL_DIRECTORY` needs `\\\\` and the `.nsh` path needs doubled backslashes because CPack writes values unescaped into `CPackConfig.cmake`.
- The Cosmyx build made on the upstream values (key `OrcaSlicer`, publisher `SoftFever`) cannot be told from upstream and is deliberately not removed.
- The file association ProgID, D-Bus names, bundle id and Flatpak app id are still shared with upstream.
- v2.5.1 pass: rebased clean (3-way merge absorbed the Flatpak guard difference). In the integration merge it conflicts with logs (T12) on `SLOTS_BY_AREA` and decision 0003; resolved by union at merge time.
- v2.5.2 pass: clean. v2.5.2 rewrote the first line of `migrate_flatpak_legacy_datadir` to `if (!is_running_in_flatpak())` (new helper in `utils.cpp`, which also gains Wayland helpers and new `[utils]` tests); the skip hook stays the next statement and the new upstream tests do not read the data folder. Integration union conflicts replayed by `rerere`.

## Shared files with other branches

- `GUI_App.cpp`: includes of version (line 2), dark (line 3), goldens (line 4) are in the other stack; this branch is placed after `Downloader.hpp` to avoid them. `SetAppName` neighbourhood is also patched by the product-name branding (it edits the commented `SetAppDisplayName` line).
- `CMakeLists.txt` (top level): CPack block also touched by the branding (appends `CPACK_NSIS_DISPLAY_NAME`) and by signing (upstream's `CPACK_NSIS_EXTRA_PREINSTALL_COMMANDS`).
- `CHANGELOG.md` (slot T17, repo area), `wiki/decisions` 0180 to 0185 (and whichever of 0001 to 0005 the foundation owns), `justfile`, `.github/workflows/cosmyx-checks.yml`, `scripts/cosmyx/{decisions.py,run_script_tests.py,tests/test_foundation.py}`, `tests/libslic3r/test_utils.cpp` (only this branch).
- Foundation hooks and Cosmyx modules are identical in every Cosmyx branch.
