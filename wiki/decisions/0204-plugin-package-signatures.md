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
  OpenSSL calls run between `ERR_set_mark()` and `ERR_pop_to_mark()`: a
  refused key or signature leaves nothing on the thread's error queue, which
  the next TLS call on the download thread would otherwise misread. The
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
  The key is stored as 64 lowercase hex; the setter refuses anything else. A
  stored key that cannot be read (hand-edited, truncated) gives no key and no
  opt-in, so that server is refused: a pin never falls back to unverified
  plugins.
- **Canonical or refused addresses.** The cloud agent hands its API address,
  with a path appended, to libcurl, which decodes a percent-encoded host,
  drops user info, removes dot segments and guesses http for an address with
  no scheme. Teaching the client every such spelling is a race it cannot win,
  so an address is read only when it is plainly `scheme://host[:port][/path]`
  (`parse_server_address()` in `logic/CloudServer.*`): an explicit http or
  https scheme, an ASCII host of letters, digits, `-`, `_` and dots or an
  `[IPv6]` literal, an optional port 1-65535, a path with no `.` or `..`
  segment, and no `%`, `@`, `?`, `#`, backslash, whitespace, control or
  non-ASCII character anywhere. Its one spelling (`normalize_server_url()`)
  has the scheme and host in lower case and drops the host's trailing dot,
  the default port, the port's leading zeros and trailing slashes; the path
  keeps its case. Any other address is unrecognised: every plugin package
  from it is refused with `unrecognised_server`, and neither the build's keys
  nor any pin or opt-in of the user applies (no pin is stored or read for
  it). That includes an address with no scheme, which earlier read as https.
- **The Cosmyx host is decided by the parsed host.** An address whose
  lower-cased host is the host of `CLOUD_SERVER_URL` is the Cosmyx server
  when it is https on the default port, whatever its path: the build's keys
  only. Plain http or any other port on that host is refused as
  unrecognised rather than treated as a custom server, so a user's pin or
  opt-in never applies to a package fetched from the Cosmyx host, and a
  package from it never travels over plain http. Another host, even under
  the same domain, is a custom server.
- **Preferences agree.** `check_cloud_url()` also requires
  `parse_server_address()` to accept the address (`Invalid` otherwise), so
  Preferences never takes an address whose plugins would all be refused; a
  query or fragment, accepted before, is now refused. An `orca_api_url`
  written by hand in the app config can still be anything, and is then
  refused for plugins by the rule above.
  The settings do not fetch `/pkg/v1/keys`: the user pastes the key from it,
  and the key id is shown to compare with the operator's.
- **Requested version.** The request carries the version asked for when it is
  a strict `X.Y.Z`, or none for the latest. Any other requested version is
  refused with `wrong_version` instead of being sent as a request for the
  latest (`request_version()`).
- **Anti-rollback.** Before the verification, a version lower than the one in
  the installed package's record is refused with `downgrade`. The upstream UI
  has no way to choose a downgrade, so the hook always passes "not chosen";
  the logic takes the flag for when one exists.
- **Record.** A package that passed is remembered under its plugin id and
  SHA-256 (two plugins may ship the same bytes). After the install,
  `PluginManager::install_cloud_plugin_package()` calls
  `CloudInstallScope::commit()`, which writes `.cosmyx_package.json`
  (`plugin_id`, `version`, `sha256`, `size`, `key_id`, `key_id` empty when
  unverified) for the exact bytes that passed: the record is matched by the
  plugin id and the SHA-256 and size of the installed file, and used once. The
  file is a denied filename for plugins (`PluginAuditManager`); the denial
  matches by prefix, so the `.cosmyx_package.json.tmp` written on the way is
  denied too. A record that cannot be written leaves no temporary file.
- **Only checked bytes stay installed.** The check runs on the downloaded body,
  which upstream then writes to a file in the temporary folder and installs
  later, so the file could be swapped in between. The commit hashes the
  installed copy, inside the user's plugin folder, and refuses the install
  when no record matches it or the record cannot be written.
- **Metadata are read again from the installed bytes.** The installer reads
  the dependencies and the entry package from the temporary file before it
  copies it, so a file swapped there and swapped back before the copy would
  pass the digest check with another package's dependencies. The commit reads
  both again from the installed copy, the bytes whose digest it checks, and
  refuses the install when they differ from what the installer read. This was
  chosen over writing the body to a private temporary folder: that would need
  a rewrite of upstream's temporary file code in `CloudPluginService.cpp`, and
  it only keeps out other users, who cannot replace a file in a per-user or
  sticky temporary folder anyway; the re-read closes the window up to the
  plugin folder itself, which anyone able to write has already won.
- **A refused install leaves the plugin not installed.** On a refusal the
  hook returns before upstream marks the plugin entry installed, enabled and
  without error: the installed package file is removed, a fresh install keeps
  its not-installed entry with the error set, and an update reports
  `ReplacementInstalled` (the old package was already replaced), so its caller
  marks the plugin broken instead of restoring old grants. Four hook lines.
- **The version floor survives a refusal.** The upstream installer moves the
  replaced plugin folder aside and deletes it once the new one is in place,
  record included, so a refused update would lose the anti-rollback anchor.
  A `Cosmyx::CloudInstallScope`, opened at the top of
  `install_cloud_plugin_package()` with the plugin entry, reads the record of
  the package being replaced before anything moves; a refused commit writes
  it back in the new folder (`refuse_installed_package()`) instead of leaving
  none, so the next download of an older version is still a downgrade. The
  scope also drops the remembered records of the plugin when the install
  ends, so a failed install leaves none behind. A record left by a download
  that failed after its check (writing the temporary file) lives until the
  next install of that plugin ends, and can only ever match the bytes it was
  checked for.
- **No stale wheel extraction.** The specification asks that a stale
  `__whl_extracted__` is never reused. Upstream's installer already meets it:
  it moves the replaced plugin folder aside and installs into a fresh one, and
  a wheel is extracted next to it in that folder, so the commit removes
  nothing.
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
  `no_pinned_key`, `unrecognised_server` (see above), `no_row` (the row did
  not reach the check) and
  `unknown_slot` (the build cannot name its os/arch in the protocol's
  vocabulary, so it cannot verify).

## Consequences

- Until a release pins the production key, cloud plugins from the Cosmyx
  server cannot be installed or updated. Plugins already installed keep
  working. A development server can be tested as a custom instance with its
  key pinned, or with unverified plugins allowed.
- Two installs of the same plugin at the same time are not supported
  upstream either; the scope of the one that ends first drops the other's
  record, and the other is then refused, never installed unchecked.
- Not done here: an "unverified" badge in the plugin list for legacy and
  unverified installs (the list is a web page outside the Cosmyx folders; the
  state is readable through `read_package_record()`), a "fetch key from
  server" button, and a user-chosen downgrade.
- An address that reaches the Cosmyx server under another name (an IP
  literal, a DNS alias) is a custom server: the user's pins for it apply.
  TLS host name checking makes such a name fail unless the certificate covers
  it. Once `PRODUCTION_KEYS` is filled, the breaker test that expects the
  build's keys for a refused Cosmyx spelling must expect no key instead.
- Removing it: delete the hook lines tagged `// Cosmyx` in
  `OrcaCloudServiceAgent.{hpp,cpp}`, `CloudPluginService.cpp`,
  `PluginManager.cpp` (the scope and the commit block), `PluginAuditManager.cpp`, `PluginFsUtils.cpp` and
  `PluginLoader.cpp`, the files `logic/PluginSigning.*`,
  `logic/PluginTrust.*` and `PluginVerify.*`, `parse_server_address()` and
  its use in `check_cloud_url()` (`logic/CloudServer.*`), the plugin rows of
  `CloudServerPrefs.cpp`, and their tests.
- Checked by `cosmyx_tests` (`test_cosmyx_plugin_signing.cpp`,
  `test_cosmyx_plugin_trust.cpp`, and the breakers' reproductions
  `test_cosmyx_plugin_signing_break_a.cpp`,
  `test_cosmyx_plugin_trust_break_b.cpp`, `test_cosmyx_plugin_break_c.cpp`,
  and the address rules in `test_cosmyx_cloud_server.cpp`); the hook lines are pinned by
  `scripts/cosmyx/tests/test_plugin_signing.py`. The Preferences rows are to
  be covered by the GUI goldens (T16), which are not on this branch's base.
