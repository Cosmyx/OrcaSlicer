# 0201. CosmoCloud server defaults

## Status

Accepted.

## Context

The Orca cloud agent (`OrcaCloudServiceAgent`) reads the app keys
`orca_api_url`, `orca_auth_url`, `orca_cloud_url` and `orca_pub_key` once, in
`configure_urls()`, when `create_agent_from_config()` creates it, and keeps
its upstream defaults (`api`, `auth` and `cloud.orcaslicer.com`) for an empty
key. CosmoCloud speaks the same protocol and serves the API, the auth server
and the web pages from one host, `https://orca-cloud.cosmyx3d.fr`. The user
decided that values set by the user always win.

The hook must run before the agent is created. The T17 hook in
`GUI_App::init_app_config()` (`Cosmyx::use_vendor_data_dir()`) runs early
enough, but lives on another branch (`feat/cosmyx-install-paths`); this
branch is stacked on `feat/cosmyx-stealth-mode` only, so it cannot reuse it.

## Decision

- `Cosmyx::apply_cloud_server(AppConfig&)`
  (`src/slic3r/GUI/Cosmyx/logic/CloudServer.cpp`, wxWidgets-free) fills the
  four keys with `CLOUD_SERVER_URL` (three times) and `CLOUD_PUB_KEY`.
- A key gets the CosmoCloud value only when it is empty, or still holds the
  value Cosmyx wrote there last time, remembered under
  `cosmyx_seeded_<key>`. Any other value was set by the user and is kept. A
  later change of a constant therefore reaches existing installs, and never a
  user's value. While the custom instance of decision 0203 is on, only empty
  keys are filled.
- `GUI_App.cpp` gets one call line right before
  `create_agent_from_config()` in `on_init_network()`, the only place the
  agent is created (also reached by `restart_networking()`), and one include
  line after `#include "OrcaCloudServiceAgent.hpp"`, away from the lines other
  Cosmyx branches add at the top of the file.
- The web pane fallback `kCloudUrl` in `WebViewDialog.cpp` ignores the app
  config; it is rewritten to `https://orca-cloud.cosmyx3d.fr` by a build-time
  branding patch row (`cosmyx-src/branding/product-name/patches.json`, on
  `feat/cosmyx-product-name`), not by a hook here. Rows on the same table do
  the same for the fallbacks used only when the agent has no web URL
  (`Plater.cpp`, `PluginsDialog.cpp` twice, `PluginResolver.cpp`).

## Consequences

- With stealth mode off, sign-in, sync and the plugin hub talk to CosmoCloud.
- The keys are stored in the configuration file, so a user can edit them by
  hand or from Preferences (decision 0203).
- `cosmyx_tests` (`test_cosmyx_cloud_server.cpp`) checks the fill rules;
  `scripts/cosmyx/tests/test_cloud_server.py` pins the hook lines.
- Removing it: delete the two hook lines in `GUI_App.cpp` and
  `CloudServer.{hpp,cpp}`; stored keys then keep pointing at CosmoCloud until
  the user clears them.
