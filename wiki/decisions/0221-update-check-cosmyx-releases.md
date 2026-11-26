# 0221. Update check on the Cosmyx releases

## Status

Accepted.

## Context

Upstream checks for a new version at startup and from Help > Check for
Updates (also the macOS app menu), all through
`GUI_App::check_new_version_sf()`. It queries
`https://check-version.orcaslicer.com/latest` (`AppConfig.cpp`), compares the
answer with `SoftFever_VERSION`, may offer a pre-release when the user did not
tick "Check for stable updates only", and runs even in Stealth mode. A Cosmyx
build must not be offered an OrcaSlicer release, must compare its own version
(`<base>-<patch>`, decision 0060), and must stay offline in Stealth mode.

The user decided:

- the source is the GitHub releases of Cosmyx/OrcaSlicer;
- only release builds are ever offered: never a draft, a pre-release, a dev or
  a nightly build, whatever the user's "stable updates only" setting says;
- the check does not run in Stealth mode.

## Decision

- Release tags follow `v<OrcaSlicer base>.<Cosmyx patch>`, for example
  `v2.5.2.8` for the display version `2.5.2-8`. Exactly four ASCII decimal
  numbers without leading zeros (decision 0064); any other tag, such as the
  old `v3.0` and `v4.0` tags of the fork, is ignored.
- `check_new_version_sf()` starts with one hook line,
  `Cosmyx::check_for_update(*app_config, by_user, version_info); return;`,
  in `src/slic3r/GUI/Cosmyx/UpdateCheckRequest.cpp`. The upstream body stays
  in place, unreachable, so the hunk is one line. The URL lives in
  `logic/UpdateCheck.hpp` (`update_check_url`), not in `AppConfig.cpp`: the
  hook replaces the whole request, so the upstream constant and its
  `version_check_url` override are not read any more and need no patch row.
- The logic in `logic/UpdateCheck.{hpp,cpp}` (unit tested by `cosmyx_tests`)
  reads the releases array, drops drafts, pre-releases and tags outside the
  convention, and keeps the newest release newer than the running build. A
  release on a newer base is newer whatever its patch; on the same base it is
  newer when the build has a higher patch, or when the build is an upstream
  pre-release of that base (`2.6.0-dev-9` is older than the `2.6.0.8`
  release).
- The popup is the upstream `UpdateVersionDialog`, raised through
  `EVT_SLIC3R_VERSION_ONLINE` from the main thread, with the version shown and
  stored in `skip_version` in the display form `2.5.2-8`. The upstream handler
  compares `skip_version` as text, which gets `2.5.2-10` and `2.5.2-9` wrong,
  so the Cosmyx code compares the numbers itself: a skipped release stays
  quiet at startup, and an older `skip_version` is cleared before the event.
  The event carries `by_user`, so a check the user asked for shows a skipped
  release anyway (without the Skip button), where upstream showed nothing.
- The "Check for stable updates only" box of the popup is hidden by one hook
  line in `ReleaseNote.cpp`: the setting no longer changes anything, and a box
  that does nothing would mislead.
- Stealth mode (`AppConfig::get_stealth_mode()`, decision 0200 on
  `feat/cosmyx-stealth-mode`'s line): the startup check does nothing, and
  Help > Check for Updates shows a message that the check is off while
  Stealth mode is on and where to turn it off. The menu item stays enabled
  rather than greyed out: disabling it would need a hook in the menu code of
  `MainFrame.cpp` and another in the macOS app menu, and a grey item does not
  tell the user why.
- `publish_release.yml`: its upstream download and assemble steps look for
  `OrcaSlicer_*` artifacts, while Cosmyx builds name them `CosmoSlice_*`
  (decision 0210). Those two steps get `if: ${{ false }} # Cosmyx`, and three
  `# Cosmyx` steps run `scripts/cosmyx/release_publish.py` instead:
  - `prepare`, before the upstream draft check: refuses a tag outside the
    convention and a run whose CosmoSlice artifacts carry another display
    version (so a dev build, `2.6.0-dev-8`, can never be published), refuses
    an existing release that is published or marked pre-release, and creates
    the draft on the run's commit when it does not exist yet (refusing a tag
    that already points elsewhere);
  - `download` and `assemble`: the CosmoSlice installers, portable zips,
    universal DMG, AppImages, Flatpaks and PDB archive, never the MSIX.
- Who may publish is still the upstream `RELEASE_PUBLISHER` repository
  variable; it is not set on the fork yet, so the workflow stops at its first
  step until someone sets it.

## Consequences

- Until a release exists on the fork, every check finds nothing: Help > Check
  for Updates says this is the newest version.
- GitHub's unauthenticated API allows 60 requests an hour per address; one
  request per start is far below that. An error is logged and otherwise
  silent, as upstream.
- A release is offered only once it is published and not marked pre-release
  on GitHub; publishing the draft creates the tag on the built commit.
- The update check depends on `feat/cosmyx-version` (`patch_version`,
  `compose_display_version()`); the branch is stacked on it. Stealth mode is
  read through the upstream getter, so it needs no code from
  `feat/cosmyx-stealth-mode`.
- Removing it: drop the `GUI_App.cpp` include and call, the `ReleaseNote.cpp`
  line, the `publish_release.yml` hook lines, `Cosmyx/UpdateCheckRequest.*`,
  `Cosmyx/logic/UpdateCheck.*`, `scripts/cosmyx/release_publish.py`,
  `localization/cosmyx/update-check/` and their tests.
