# 0204. Plugin package signatures

## Status

Accepted.

## Context

CosmoCloud 0.6.0 signs every plugin package row of
`POST /api/v1/plugins/download` with Ed25519 (CosmoCloud protocol "Plugin
package signatures", its decisions 0082-0090). Upstream installs whatever the
download link returns and checks nothing. CosmoCloud decision 0077 also found
an upstream bug: a wheel's entry package name (`Import-Name`, `top_level.txt`
or `Name`) is used unchecked as a folder name under `__whl_extracted__`, so
`Import-Name: ../../escape` writes outside the plugin folder.

The production signing key is not known yet, the same situation as the public
API key (decision 0202). A custom orca-cloud instance (decision 0203) has its
own key, or none at all.

## Decision

- **Verification.** `src/slic3r/GUI/Cosmyx/logic/PluginSigning.{hpp,cpp}`
  (wxWidgets-free, OpenSSL and nlohmann::json) implements the protocol's ten
  steps in order, with its reason strings: Ed25519 with
  `EVP_PKEY_new_raw_public_key(EVP_PKEY_ED25519)` and a one-shot
  `EVP_DigestVerify` with a NULL digest, `CRYPTO_memcmp` for the digest. The
  CosmoCloud vectors are copied unchanged to
  `tests/cosmyx/data/plugin-signatures.json`; every row must give its
  `expect`.
- **The row reaches the check whole.** `PluginDownloadData` gets one field,
  `cosmyx_row`, the row as parsed, instead of one field per signed value: the
  rules depend on JSON types (`5.0` and `true` are not sizes, a `null`
  `signatures` is not an absent one), which typed fields would lose.
- **Where it runs.** `CloudPluginService::download_cloud_plugin()` calls
  `Cosmyx::verify_cloud_plugin_package()` after the empty-body check and
  before the `PK` sniff and the temporary file: install and update both pass
  there, and a refused package is never written. Any result other than `ok`
  refuses, with no fallback.
- **Pinned keys.** `PRODUCTION_KEYS` in `PluginSigning.hpp` is the build's
  table, and `REVOKED_KEY_IDS` its revoked list. Both are empty: the
  production key is not provided. While `PRODUCTION_KEYS` is empty, every
  install or update from the Cosmyx server is refused with `no_pinned_key`,
  and the message says the build has no signing key. The release step is to
  add `{key_id, public_key}` from `just plugin-keys` on the production server;
  a test recomputes each key id. `scripts/cosmyx/tests/test_plugin_signing.py`
  warns while the table is empty, as 0202 does for the API key. The vector
  keys live in the tests only, and a test checks they never reach the table.
  Nothing is fetched at run time.
- **Custom server policy.** The build's pins cover `CLOUD_SERVER_URL` only;
  nothing the user stores for that address is used. For any other API
  address (the one the cloud agent was created with, `active_api_url()`):
  - a public key the user pinned for that address in Preferences ("Plugin
    signing key", with its key id shown) gives full verification;
  - with no key, the package is refused (`no_pinned_key`), unless the user
    turned on "Allow unverified plugins from this server". That still runs
    every step but the signature ones (row fields, plugin, version, platform,
    size, SHA-256, kind), logs a warning line and shows an "installed
    unverified" notification;
  - a pinned key always means full verification: the opt-in never turns a
    failed signature into an unverified install.

  The pins are kept in the app key `cosmyx_plugin_trust`, JSON keyed by the
  normalized API address, so they never follow the user to another server.
  The settings do not fetch `/pkg/v1/keys`: the user pastes the key from it,
  and the key id is shown to compare with the operator's.
- **Anti-rollback.** Before the verification, a version lower than the one in
  the installed package's record is refused with `downgrade`. The upstream UI
  has no way to choose a downgrade, so the hook always passes "not chosen";
  the logic takes the flag for when one exists.
- **Record.** After the install, `PluginManager::install_cloud_plugin_package()`
  calls `Cosmyx::commit_cloud_plugin_record()`, which writes
  `.cosmyx_package.json` (`plugin_id`, `version`, `sha256`, `size`, `key_id`,
  `key_id` empty when unverified) for the exact bytes that passed: the record
  is matched by the SHA-256 of the installed file, and used once. The same call
  removes `__whl_extracted__`, so the first load extracts the new wheel. The
  file is a denied filename for plugins (`PluginAuditManager`).
- **Legacy installs.** A plugin installed before this change has no record. It
  keeps loading as before; its next update passes the full check like any
  other download, and nothing is ever trusted from its hash.
- **Entry package guard.** `Cosmyx::check_wheel_import_name()` runs where the
  entry package is chosen (`read_wheel_plugin_metadata()`) and, for a wheel
  entry, in `plugin_loader::import_plugin_module()` right before the import,
  since the catalog sets the entry package of a cloud plugin after the
  metadata check. The second hook is not in
  `PythonInterpreter::load_module_from_whl()`, where the name becomes a path:
  upstream main removes that function (wheels installed with uv, with its own
  `is_valid_entry_package()`), so a hook there would conflict. The name must
  be an ASCII identifier (`[A-Za-z_][A-Za-z0-9_]*`, at most 255 bytes, so
  dotted names are refused, as the server does), not a dunder, not a Windows
  device name, and the wheel must hold `name/...` or `name.py` at its top. A
  namespace package folder is accepted, unlike the server's upload rule, so
  existing local wheels keep loading; the identifier rule alone closes the path
  escape.
- **Fork-only reasons**, outside the server vectors: `downgrade`,
  `no_pinned_key`, `no_row` (the row did not reach the check) and
  `unknown_slot` (the build cannot name its os/arch in the protocol's
  vocabulary, so it cannot verify).

## Consequences

- Until a release pins the production key, cloud plugins from the Cosmyx
  server cannot be installed or updated. Plugins already installed keep
  working. A development server can be tested as a custom instance with its
  key pinned, or with unverified plugins allowed.
- Not done here: an "unverified" badge in the plugin list for legacy and
  unverified installs (the list is a web page outside the Cosmyx folders; the
  state is readable through `read_package_record()`), a "fetch key from
  server" button, and a user-chosen downgrade.
- Removing it: delete the hook lines tagged `// Cosmyx` in
  `OrcaCloudServiceAgent.{hpp,cpp}`, `CloudPluginService.cpp`,
  `PluginManager.cpp`, `PluginAuditManager.cpp`, `PluginFsUtils.cpp` and
  `PluginLoader.cpp`, the files `logic/PluginSigning.*`,
  `logic/PluginTrust.*` and `PluginVerify.*`, the plugin rows of
  `CloudServerPrefs.cpp`, and their tests.
- Checked by `cosmyx_tests` (`test_cosmyx_plugin_signing.cpp`,
  `test_cosmyx_plugin_trust.cpp`); the hook lines are pinned by
  `scripts/cosmyx/tests/test_plugin_signing.py`. The Preferences rows are to
  be covered by the GUI goldens (T16), which are not on this branch's base.
