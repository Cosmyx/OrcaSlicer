# feat/cosmyx-plugin-signing (PR #112)

## Purpose

Cloud plugins are installed or updated only when their CosmoCloud package signature verifies (CosmoCloud 0.6.0 signs every
row of `POST /api/v1/plugins/download` with Ed25519), and never as an older version than the one installed. Also closes the
upstream wheel `Import-Name` path escape (CosmoCloud decision 0077). Decision 0204 (and an edit to 0203). Changelog: a second
line under cloud-server's slot T18 (no own slot), flagged **Breaking**.

## Parent and dependencies

- Parent: `feat/cosmyx-cloud-server` (PR #109, stacked). Range `origin/feat/cosmyx-cloud-server..origin/feat/cosmyx-plugin-signing`
  has 23 commits, oldest `7583922463` (feature), `7365a578d8` (tests), `c9298f1964` (decision, changelog), breaker rounds
  `3730e75a1b`..`078373b601`, tip `3a16c1e3c3` (changelog PR link). Notable: `af36754242` (`crypt32` on Windows),
  `c96c5eb130` (no-app behaviour, resource-only wheels), `078373b601` (latch).
- Extends cloud-server's Cosmyx files: `logic/CloudServer.{hpp,cpp}` (`server_kind()` Cosmyx / custom / unrecognised,
  canonical address rule, `active_api_url()`), `CloudServerPrefs.cpp` (signing key and unverified opt-in rows).
- Upstream facts it relies on: `PluginDownloadData` and `OrcaCloudServiceAgent::get_plugin_download_url()` row parsing;
  `CloudPluginService::download_cloud_plugin()` (empty-body check, then `PK` sniff and temp file);
  `PluginManager::install_cloud_plugin_package()` (`CloudUpdateFailure::ReplacementInstalled`, `set_plugin_error`);
  `PluginAuditManager::default_denied_filenames()`; `read_wheel_plugin_metadata()` in `PluginFsUtils.cpp`;
  `import_plugin_module()` in `PluginLoader.cpp`; OpenSSL 3 (`EVP_PKEY_new_raw_public_key`, `EVP_DigestVerify`,
  `ERR_set_mark`/`ERR_pop_to_mark`); `wxModule`, `GUI_App`, `wxTheApp`.

## Changes

| File | Kind | What the change does |
|---|---|---|
| `src/slic3r/Utils/OrcaCloudServiceAgent.hpp` | upstream hook (1 line) | `nlohmann::json cosmyx_row;` appended to `struct PluginDownloadData` after `returned_os`. |
| `src/slic3r/Utils/OrcaCloudServiceAgent.cpp` | upstream hook (1 line) | `row.cosmyx_row = item;` after `row.returned_os = ...` in `get_plugin_download_url()`. |
| `src/slic3r/plugin/CloudPluginService.cpp` | upstream hook (7 lines) | Include `PluginVerify.hpp` as line 2; `cosmyx_item` pointer declared with the result vectors, set in the row loop; `verify_cloud_plugin_package(...)` call after the empty-body check, before the `PK` sniff. |
| `src/slic3r/plugin/PluginManager.cpp` | upstream hook (6 lines) | Include line 2; `CloudInstallScope cosmyx_scope(descriptor)` first in `install_cloud_plugin_package()`; `cosmyx_scope.commit(installed, error)` block before `installed.version = requested_version`. |
| `src/slic3r/plugin/PluginAuditManager.cpp` | upstream hook (1 line) | `.cosmyx_package.json` added to `default_denied_filenames()` after `.install_state.json`. |
| `src/slic3r/plugin/PluginFsUtils.cpp` | upstream hook (3 lines) | Include `logic/PluginTrust.hpp` line 2; `check_entry_package_name()` after the entry package is chosen in `read_wheel_plugin_metadata()`. |
| `src/slic3r/plugin/PluginLoader.cpp` | upstream hook (3 lines) | Include line 2; `check_entry_package()` before the wheel import in `import_plugin_module()`. |
| `src/slic3r/GUI/Cosmyx/logic/PluginSigning.{hpp,cpp}` | Cosmyx-owned (wx-free) | The protocol's ten steps; `PRODUCTION_KEYS` and `REVOKED_KEY_IDS` (both empty). |
| `src/slic3r/GUI/Cosmyx/logic/PluginTrust.{hpp,cpp}` | Cosmyx-owned (wx-free) | Per-server pins (`cosmyx_plugin_trust` app key, JSON keyed by normalized API address), record, anti-rollback, entry package guard. |
| `src/slic3r/GUI/Cosmyx/PluginVerify.{hpp,cpp}` | Cosmyx-owned | `verify_cloud_plugin_package()`, `CloudInstallScope`, `package_gate()` latch (`Unchecked` / `Checked` / `AppGone`) set by a `wxModule`. |
| `src/slic3r/GUI/Cosmyx/logic/CloudServer.*`, `CloudServerPrefs.cpp` | Cosmyx-owned (edited) | Canonical-or-refuse address rule shared with Preferences; Preferences rows for the key pin and the opt-in. |
| `tests/cosmyx/CMakeLists.txt` | foundation file (edited) | `OpenSSL::Crypto` on the `cosmyx_tests` link line; `crypt32` on `WIN32`. |
| `tests/cosmyx/test_cosmyx_plugin_*.cpp`, `test_cosmyx_server_address.cpp`, `test_cosmyx_cloud_server.cpp`, `data/plugin-signatures.json` | test | Catch2 cases, breaker files A-E, the CosmoCloud vectors copied unchanged. |
| `scripts/cosmyx/tests/test_plugin_signing.py` | test | Pins every hook line and count; vector format; vector keys never in the production table; warns while `PRODUCTION_KEYS` is empty. |
| `wiki/decisions/0204-plugin-package-signatures.md`, edit of `0203` | docs | Decision; 0203 loopback wording. |
| `CHANGELOG.md` | data | Second line under T18. |

Upstream hooks: 22 lines in 7 files, all tagged `// Cosmyx`.

## Rebase risk zones

| Upstream anchor | Risk |
|---|---|
| `PluginDownloadData` fields and the row parse in `get_plugin_download_url()` (~line 3790 on DEV) | the plugin API is young upstream; a renamed field moves the hook line |
| `download_cloud_plugin()`: empty-body check, `PK` magic sniff, temp file | the call must stay after the body is complete and before anything is written |
| `install_cloud_plugin_package()` signature and `CloudUpdateFailure` | the commit block uses `failure` and `set_plugin_error` |
| `read_wheel_plugin_metadata()`, `import_plugin_module()` | entry package choice and the `.whl` branch |
| Plugin subsystem on a release tag | `src/slic3r/plugin/` may be older or absent on a tag; check each anchor exists before replaying |

## Intent to preserve

- Any verification result other than `ok` refuses, with no fallback; a pinned key always means full verification.
- `PRODUCTION_KEYS` stays empty until the user provides the production key (`just plugin-keys` on the server); never add a
  vector key to it.
- Pins belong to one normalized API address; an address that is not canonical is refused, never trimmed or guessed.
- Without an app ever seen (upstream `slic3rutils_tests`), behaviour equals upstream; once seen, the check stays on
  (fail closed after the app is gone).
- The record `.cosmyx_package.json` stays a denied filename; the version floor survives a refused update.

## Verification

- `ctest -C Release -R cosmyx` (Catch2 `[cosmyx]` plugin cases); upstream `slic3rutils_tests` must stay green.
- `just test-scripts` (`test_plugin_signing.py`, `test_cloud_server.py`); `just decisions`.
- C++ builds only in CI (`build_all.yml`); Windows needs `crypt32` for the tests link.

## Known pitfalls

- `af36754242`: `cosmyx_tests` failed to link on Windows (static OpenSSL `Cert*` symbols) until `crypt32` was linked.
- `1066b61825`: a refused signature left the OpenSSL error queue dirty and broke the next TLS call on the download thread.
- `c96c5eb130` / `078373b601`: the upstream plugin tests run without an app; refusing there fails them, so the latch exists.
- The changelog line sits under T18 next to cloud-server's line: keep both.

## Shared files with other branches

- `logic/CloudServer.*`, `CloudServerPrefs.cpp`, `tests/cosmyx/test_cosmyx_cloud_server.cpp`, decision 0203: parent
  cloud-server's files.
- `tests/cosmyx/CMakeLists.txt`: foundation's file (link line only).
- `CHANGELOG.md` slot T18 (shared with cloud-server).
