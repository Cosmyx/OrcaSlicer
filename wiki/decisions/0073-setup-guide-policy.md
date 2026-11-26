# 0073. Setup guide skips the stealth and network plugin pages

## Status

Accepted.

## Context

The setup guide (`WebGuideDialog`, pages in `resources/web/guide/`) ends on
page 22 (filaments). `22/22.js` shows a Finish button when the profile says
the network plugin is installed and compatible
(`network_plugin_install == '1'` and `network_plugin_compability != '0'`);
otherwise it shows Next, which leads to the stealth mode page (`4orca/`) and
then to the network plugin page (`5/`). The old fork edited `22.js` to swap
the buttons.

The two keys are set in `GuideFrame::SaveProfileData()` from
`installed_networking` and `is_compatibility_version()`. In
`WebGuideDialog.cpp` and in the guide pages they are only read by `22.js`.
The network plugin download is only started at `user_guide_finish` when
`InstallNetplugin` is true, and that flag is only set by the
`network_plugin_install` command sent by page 5 with "yes". The internal
`network_plugin_ready` flag is computed separately and is not touched.

## Decision

- `Cosmyx::apply_guide_policy(json& profile, bool& stealth)`, header-only in
  `src/slic3r/GUI/Cosmyx/logic/GuidePolicy.hpp`, sets the dialog's
  `StealthMode` to true and the profile's `stealth_mode` to true,
  `network_plugin_install` to "1" and `network_plugin_compability` to "1".
- It is called once, right after
  `m_ProfileJson["stealth_mode"] = StealthMode;` in `SaveProfileData()`,
  through one hook line; the include goes after the file's first include.
- No guide page is edited. Reporting the plugin as installed only changes
  which button `22.js` shows; it starts no download and no install, so no
  safer way was needed.
- `SaveProfile()` then stores `stealth_mode` true, which matches the forced
  getter (decision 0070).

## Consequences

- The guide never shows the stealth mode or network plugin pages. The Bambu
  network plugin can still be installed later from the application, where
  stealth mode keeps its cloud features off.
- If `SaveProfileData()` throws before the hook, the guide falls back to the
  upstream buttons; stealth mode stays forced by the getter.
- Removing it: delete `GuidePolicy.hpp`, the two hook lines in
  `src/slic3r/GUI/WebGuideDialog.cpp` and the policy checks in
  `tests/cosmyx/test_cosmyx_stealth.cpp`.
