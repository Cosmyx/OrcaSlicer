# feat/cosmyx-cloud-server (PR #109)

## Purpose

Cosmyx runs its own orca-cloud compatible server, CosmoCloud, at `https://orca-cloud.cosmyx3d.fr`. This branch makes the
application use it for sign-in, profile sync and the plugin hub, lets the user turn stealth mode off again (it stays ON
until the user opts out), and adds a Preferences panel to point the app at a custom orca-cloud instance. User-set cloud
addresses always win over the CosmoCloud defaults. Decisions 0200 (supersedes 0070 and 0071), 0201, 0202, 0203. PR title:
"point the cloud at CosmoCloud and add a custom orca-cloud instance setting".

## Parent and dependencies

- Parent: `feat/cosmyx-stealth-mode` (PR #94, stacked). Range `origin/feat/cosmyx-stealth-mode..origin/feat/cosmyx-cloud-server`
  has seven commits: `d27654d24f` (getter), `f7f9f3f2de` (CloudServer defaults), `88d9f1d0b5` (Preferences panel),
  `ff0efff25a` (tests), `f0478fe446` (docs), `212c04b070` (loopback http), `ed15f92456` (hook-count test fix).
- It rewrites the hook line added by the parent, so it cannot be rebased before the parent.
- Companion on `feat/cosmyx-product-name` (PR #103), commit `1310e1099f`: four build-time patch rows (five literal sites)
  rewriting the cloud URL fallbacks `https://cloud.orcaslicer.com` to `https://orca-cloud.cosmyx3d.fr`
  (`WebViewDialog.cpp` `kCloudUrl`, `Plater.cpp`, `PluginsDialog.cpp` twice, `PluginResolver.cpp`). They are not in this
  branch; without them a web pane reset loads the upstream cloud.
- `feat/cosmyx-install-paths` (T17) is NOT a dependency: its early `use_vendor_data_dir()` hook was avoided on purpose.
- Upstream APIs, keys and classes it relies on: `GUI_App::on_init_network(bool try_backup)` and the single call to
  `Slic3r::create_agent_from_config(data_directory, app_config)` (`NetworkAgentFactory.cpp:208`), also reached through
  `restart_networking()`; `OrcaCloudServiceAgent::configure_urls(AppConfig*)` which reads the app keys `orca_api_url`,
  `orca_auth_url`, `orca_cloud_url` (base URLs; empty key keeps the upstream default) and `orca_pub_key` (sent as the
  `apikey` auth header); `AppConfig::get_stealth_mode()`, `get_bool("firstguide","finish")`, `get_bool("stealth_mode")`,
  `AppConfig::has/set/set_bool/get`; `PreferencesDialog::create_items()` Online tab, the `item_network_test` row and
  `g_sizer`, `m_parent`; wx widgets and `_L()` strings.

## Changes

| File | Kind | What the change does |
|---|---|---|
| `src/libslic3r/AppConfig.cpp` | upstream hook | Include `#include "Cosmyx/StealthMode.hpp" // Cosmyx` right after `#include "AppConfig.hpp"` (NOT line 2: `feat/cosmyx-dark-default` has its own include at the top of this file). The first statement of `bool AppConfig::get_stealth_mode()` becomes `    return Cosmyx::stealth_mode(*this); // Cosmyx: on until the user opts out (decision 0200)`, replacing the parent's `return true;`. Upstream body stays below it, unreachable. |
| `src/slic3r/GUI/GUI_App.cpp` | upstream hook | Include `#include "Cosmyx/logic/CloudServer.hpp" // Cosmyx` directly after `#include "OrcaCloudServiceAgent.hpp"` (top of file, away from lines other branches add); call `    Cosmyx::apply_cloud_server(*app_config); // Cosmyx: CosmoCloud unless the user set a server (decision 0201)` in `bool GUI_App::on_init_network(bool try_backup)`, directly BEFORE `std::unique_ptr<Slic3r::NetworkAgent> agent_ptr = Slic3r::create_agent_from_config(data_directory, app_config);` and after the comment `// m_agent = new Slic3r::NetworkAgent(data_directory);`. |
| `src/slic3r/GUI/Preferences.cpp` | upstream hook | Include `#include "Cosmyx/CloudServerPrefs.hpp" // Cosmyx` as line 2 (after `#include "Preferences.hpp"`); in `PreferencesDialog::create_items()` the line `    g_sizer->Add(Cosmyx::create_cloud_server_prefs(m_parent), 0, wxEXPAND); // Cosmyx: custom orca-cloud instance (decision 0203)` right after `g_sizer->Add(item_network_test);` and before the `//// ONLINE > Cloud Providers` title. |
| `src/libslic3r/Cosmyx/StealthMode.{hpp,cpp}` | Cosmyx-owned | `Cosmyx::stealth_mode(const AppConfig&)`: true until the setup guide is finished (same first rule as upstream), then `STEALTH_MODE_DEFAULT` (true) until the configuration is seeded, then the stored `stealth_mode`. `seed_stealth_mode(AppConfig&)` writes the default once and sets the marker key `cosmyx_stealth_mode_seeded` (needed because upstream `set_defaults()` stores `stealth_mode` as false). |
| `src/slic3r/GUI/Cosmyx/logic/CloudServer.{hpp,cpp}` | Cosmyx-owned (wx-free) | Constants `CLOUD_SERVER_URL` (`https://orca-cloud.cosmyx3d.fr`) and `CLOUD_PUB_KEY` (placeholder `cosmocloud-public-key`), key lists, `apply_cloud_server(AppConfig&)` (seeds stealth, then fills the four keys only when empty or still equal to the value Cosmyx stored under `cosmyx_seeded_<key>`; while `cosmyx_custom_cloud` is on only empty keys are filled), `use_custom_cloud`, `use_cosmocloud`, `custom_cloud_enabled`, URL and key validation (`https` only, host, optional port 1-65535, no spaces or user info; plain `http` only on loopback: `localhost`, `*.localhost`, `127.0.0.0/8`, `[::1]`), value normalisation (trim, lower-case scheme, no trailing slash, scheme guess). |
| `src/slic3r/GUI/Cosmyx/CloudServerPrefs.{hpp,cpp}` | Cosmyx-owned | `create_cloud_server_prefs(wxWindow*)`: checkbox "Use your custom orca-cloud instance", four fields, Apply, per-field errors, a restart-needed message. Strings are `_L()` and extracted into the Cosmyx catalogues by `just i18n-extract` (reads `src/**/Cosmyx/**`). |
| `src/slic3r/GUI/Cosmyx/logic/GuidePolicy.hpp` | Cosmyx-owned | Comment change only: the guide still reports stealth on, now so the guide finishes in stealth mode and the user opts out later. |
| `tests/cosmyx/test_cosmyx_cloud_server.cpp`, `tests/cosmyx/test_cosmyx_stealth.cpp` | test | Catch2 cases (see Verification). |
| `scripts/cosmyx/tests/test_cloud_server.py` | test | unittest pinning hook lines and flagging the public key placeholder. |
| `scripts/cosmyx/tests/test_foundation.py` | test | Adds slot `T18` to `SLOTS_BY_AREA["GUI"]`. |
| `CHANGELOG.md` | data | Line under new `<!-- cosmyx-slot: T18 -->` in `### GUI` (after T11f). |
| `wiki/decisions/0200..0203-*.md`, edits to `0003`, `0070`, `0071` | data (docs) | Decision records; 0070 and 0071 marked superseded; 0003 lists the T18 slot. |

Config schema it writes in AppConfig: `orca_api_url`, `orca_auth_url`, `orca_cloud_url`, `orca_pub_key` (upstream keys),
`cosmyx_seeded_<key>` (last value Cosmyx wrote), `cosmyx_custom_cloud` (bool), `cosmyx_custom_<key>` (user's custom values,
kept when the box is unchecked), `cosmyx_stealth_mode_seeded`, `stealth_mode`.

## Rebase risk zones

| Upstream anchor | origin/DEV vs upstream/v2.5.1 | Churn since 2026-01-01 (DEV commits) |
|---|---|---|
| `AppConfig::get_stealth_mode()` in `src/libslic3r/AppConfig.cpp`, and the include block after `#include "AppConfig.hpp"` | exists in v2.5.1 with the identical body (`firstguide/finish` then `stealth_mode`); include block identical; file differs 2 added / 38 removed lines elsewhere | 81 |
| `GUI_App::on_init_network` and the single `create_agent_from_config(data_directory, app_config)` call | exists in v2.5.1 (definition line 4039, call line 4166; DEV 4047 / 4174). Same preceding comment `// m_agent = new Slic3r::NetworkAgent(data_directory);` | `GUI_App.cpp`: 246 commits, differs 22 / 38 lines |
| GUI_App.cpp include `#include "OrcaCloudServiceAgent.hpp"` (anchor for the include hook) | present in v2.5.1 (line 5) | as above |
| `Preferences.cpp` `create_items()`, `item_network_test`, `g_sizer->Add(item_network_test);`, "Cloud Providers" title | all present in v2.5.1 (lines 1667, 2224-2231), but the file differs 241 / 415 lines so line numbers shift; check the anchor lines still adjoin | 99 |
| `OrcaCloudServiceAgent::configure_urls` and the keys `orca_api_url/auth/cloud/pub_key` | `src/slic3r/Utils/OrcaCloudServiceAgent.cpp` identical in DEV and v2.5.1 (empty diff); keys at lines 119-122; non-empty app key overrides the default | 39 |
| `NetworkAgentFactory.cpp` `create_agent_from_config` | identical in DEV and v2.5.1; calls `configure_urls(app_config)` | 21 |
| `WebViewDialog.cpp` `kCloudUrl`, `Plater.cpp`, `PluginsDialog.cpp`, `PluginResolver.cpp` literals (patched by the product-name branch) | all four patch rows match exact counts in v2.5.1 | 27, 562, 45, 13 |
| `PresetUpdater::check_vendor_update` early return on stealth mode | present in v2.5.1 (line 1412) | 31 |

Conclusion: every anchor exists in v2.5.1; the hunks apply with line offsets. The one structural risk is another Cosmyx
branch changing the same `AppConfig.cpp` include block (dark-default).

## Intent to preserve

- Stealth mode is ON for a new install and for an install upgraded from a forced-stealth build, until the user opts out;
  after seeding, the stored `stealth_mode` decides. `STEALTH_MODE_DEFAULT` is the single constant. The setup guide still
  finishes in stealth mode (re-running the guide turns it back on, by design).
- Cloud addresses set by the user win: a key is overwritten only when empty or equal to the last value Cosmyx wrote.
  With the custom instance on, only empty keys are filled, so the agent never falls back to the upstream cloud.
- Plain `http://` is accepted only for loopback hosts (`localhost`, `*.localhost`, `127.0.0.0/8`, `[::1]`) so a local
  CosmoCloud at `http://localhost:8000` can be tested; every other host, private LAN included, needs `https`. An explicit
  scheme is never rewritten.
- The public key is a placeholder (`cosmocloud-public-key`, decision 0202). It MUST be replaced with the production key
  before a release; `test_cloud_server.py` only warns. Never print or log a production key value in docs.
- `apply_cloud_server` must run before the cloud agent is created (the agent reads the keys once). If upstream moves agent
  creation (for example into a factory or into `init_app_config`), re-place the call right before the creation, not at the
  old line. `restart_networking()` reaches creation through `on_init_network(true)`, so one placement covers both.
- If upstream rewrites `get_stealth_mode()` (new key, different class, moved to a header), do not force the old patch:
  put the Cosmyx policy call as the first statement of the new getter. If upstream rewrites the Preferences Online tab,
  re-attach the panel after whatever replaces the network test row (still within the Connection section), keeping a single
  hook line.
- If upstream changes how the cloud agent reads its URLs (renames the keys, reads them at each request), rewrite
  `CLOUD_KEYS` in `CloudServer.hpp` and the seeding accordingly.
- Changes take effect at next start; restarting the agent live was deliberately left out.

## Verification

- Catch2 `cosmyx_tests`, tag `[cosmyx]`, in `test_cosmyx_cloud_server.cpp`: "CosmoCloud serves the API, auth and web pages
  from one host", "A fresh configuration gets every CosmoCloud value", "A cloud value set by hand wins", "A value Cosmyx
  wrote follows a new CosmoCloud constant", "Applying the cloud server seeds the stealth mode default", "A custom cloud
  instance wins over CosmoCloud", "Turning the custom instance off goes back to CosmoCloud and keeps the values", "Custom
  values are empty before the first custom instance", "Cloud values are trimmed", "Cloud addresses must be https with a
  host, or http on loopback", "Plain http is accepted only on a loopback host", "The public key must be one word", "Custom
  values are normalized before they are checked". In `test_cosmyx_stealth.cpp`: "Stealth mode defaults to on", "Stealth
  mode is on before the setup guide is finished", "Stealth mode takes the Cosmyx default until it is seeded", "Seeding
  writes the default once and then follows the user", and the two guide policy cases. Run `ctest -C Release -R cosmyx`.
- `scripts/cosmyx/tests/test_cloud_server.py` (run by `just test-scripts`): `StealthHookTests` (include follows
  `#include "AppConfig.hpp"`, getter first line starts with `return Cosmyx::stealth_mode(*this); // Cosmyx`, exactly two
  stealth hook lines in `AppConfig.cpp`), `CloudServerHookTests` (one include, one call, call directly followed by the line
  containing `Slic3r::create_agent_from_config(`, a single creation site), `PreferencesHookTests` (line 1 is
  `#include "Preferences.hpp"`, line 2 is the include, panel line directly after `g_sizer->Add(item_network_test);`, exactly
  two `// Cosmyx` lines in `Preferences.cpp`), `PubKeyTests` (warning while the placeholder remains).
- `just test-scripts` also runs `test_foundation.py` slot checks (T18 in the GUI area); `just decisions` validates the register.
- Manual after a rebase: fresh profile starts in stealth mode; turn the checkbox off in Preferences and restart; sign-in
  talks to `orca-cloud.cosmyx3d.fr`; set a custom `http://localhost:8000` and see the restart message; no cloud call to
  `cloud.orcaslicer.com` (needs the product-name rows).
- C++ and the GUI compile only in CI (`workflow_dispatch` of `build_all.yml`). The Preferences panel has no GUI golden yet
  (T16, not on this base).

## Known pitfalls

- `ed15f92456`: the hook-count test counted every `// Cosmyx` line of `AppConfig.cpp`; it broke once `feat/cosmyx-dark-default`
  (also hooks this file) merged. The test now counts only lines containing `StealthMode` or `stealth_mode` (expected: 2).
  Similarly `Preferences.cpp` is asserted to hold exactly two Cosmyx lines: if another branch hooks Preferences, scope this count.
- `212c04b070`: a local CosmoCloud could not be configured because every custom address had to be https; loopback http was
  added. Do not "harden" it back.
- The include of `StealthMode.hpp` is after `#include "AppConfig.hpp"`, not on line 2, to avoid a textual conflict with
  dark-default (decision 0200 explains it).
- The foundation slot test lists every changelog slot; adding or reordering slots (T18) requires editing `SLOTS_BY_AREA` in
  `test_foundation.py` and decision 0003 in the same change.
- Stacked history: the foundation (PR #86) and the stealth-mode commits sit under this range's parent.

## Shared files with other branches

- `src/libslic3r/AppConfig.cpp`: parent stealth-mode (rewritten line) and `feat/cosmyx-dark-default` (2 hook lines).
- `src/slic3r/GUI/GUI_App.cpp`: also hooked by dark-default (4 lines), install-paths (4), version (2); the integration
  branch `ci/cosmyx-integration` totals 12 `// Cosmyx` lines there, so resolve includes at the top by keeping all.
- `src/slic3r/GUI/Preferences.cpp`: this branch only (2 lines).
- `cosmyx-src/branding/product-name/patches.json` (branch `feat/cosmyx-product-name`): carries the cloud URL fallback rows
  that complete this feature; decision 0201 points at them.
- `CHANGELOG.md` (slot T18), `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md`,
  `wiki/decisions/0070*.md`, `0071*.md` (edited from the parent's), `justfile`, localization catalogues under
  `localization/cosmyx/` (extraction of the new strings).
