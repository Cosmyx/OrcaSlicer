# 0203. Custom cloud instance in Preferences

## Status

Accepted.

## Context

Users who run their own orca-cloud server need a way to point Cosmyx at it
without editing the configuration file. The cloud agent reads the four cloud
keys only when it is created (decision 0201). User-set values must win over
the CosmoCloud defaults.

## Decision

- The Online tab of Preferences, Connection section, gets a "Custom Cloud
  Instance" checkbox; its tooltip reads "Connect to your own cloud server
  instead of Cosmyx Cloud", naming the product, not the server software. Checked, it shows four fields (API address,
  authentication address, web address, public key) and an Apply button.
- The panel lives in `src/slic3r/GUI/Cosmyx/CloudServerPrefs.{hpp,cpp}`.
  `Preferences.cpp` gets one include line after its first include and one
  call line after the network test row; no Cosmyx hook existed there before.
- Apply trims the values, writes the scheme in lower case and drops trailing
  slashes, then checks them: an address needs the https scheme, a host name,
  an optional numeric port (1-65535), and no spaces or user info; the key must
  be one non-empty word. The first error is shown under its field and nothing
  is written.
- Plain `http://` is accepted only on a loopback host, so a server run on the
  same machine (for example CosmoCloud at `http://localhost:8000`) can be
  tested without a certificate: `localhost`, any name under `.localhost`
  (RFC 6761 reserves it for loopback), `127.0.0.0/8` written as four decimal
  octets without leading zeros, and `::1` in any IPv6 spelling (decision 0204
  says why other spellings are refused). Traffic to those hosts never leaves the machine, so the
  sign-in tokens are not exposed; every other host still needs https, a
  private LAN address included. An explicit scheme is never rewritten: an
  `http://` address on another host is refused, not upgraded to https.
- An address typed without a scheme gets `http://` when its host is loopback
  (`localhost:8000` becomes `http://localhost:8000`) and `https://` otherwise,
  the scheme that host would accept. Valid values go to the four cloud keys, with a copy under
  `cosmyx_custom_<key>`, and the bool app key `cosmyx_custom_cloud` is set.
- Checking the box writes nothing until Apply succeeds.
- Unchecking it sets `cosmyx_custom_cloud` to false and writes the CosmoCloud
  values back to the four keys, owned by Cosmyx again (decision 0201). The
  custom values stay in `cosmyx_custom_<key>` and are shown again when the box
  is checked. The flag is needed because the four keys alone cannot tell a
  custom instance from CosmoCloud.
- While `cosmyx_custom_cloud` is on, `apply_cloud_server()` only fills an
  empty key, so the agent never falls back to the upstream cloud.
- A change takes effect at the next start: after Apply or unchecking, a
  message says a restart is needed. Recreating the agent at once
  (`GUI_App::restart_networking()`) was left out: it is the network plugin
  reload path, and switching servers under a signed-in session needs a
  sign-out first.
- The strings are marked with `_L` and extracted into the Cosmyx catalogues
  `localization/cosmyx/cloud-server/` by `just i18n-extract`, which reads
  `src/**/Cosmyx/**` (decisions 0081, 0085); upstream
  `localization/i18n/list.txt` is not edited. The build grafts them into the
  OrcaSlicer catalogues (decision 0080). Strings OrcaSlicer already has, such
  as "Apply" or "Restart Required", stay out of them (decision 0084).

## Consequences

- The cloud is still only used with stealth mode off (decision 0200); the
  tooltip says so.
- Removing the loopback exception: drop the http branch of
  `check_cloud_url()` and the scheme guess of `normalize_cloud_values()`.
- Validation and the configuration rules are checked by `cosmyx_tests`
  (`test_cosmyx_cloud_server.cpp`); the hook lines are pinned by
  `scripts/cosmyx/tests/test_cloud_server.py`. The panel itself is to be
  covered by the GUI goldens (T16), which are not on this branch's base.
- Removing it: delete the two hook lines in `Preferences.cpp`,
  `CloudServerPrefs.{hpp,cpp}` and the custom-instance part of
  `CloudServer.{hpp,cpp}`.
