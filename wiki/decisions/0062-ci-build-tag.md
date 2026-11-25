# 0062. CI build tag

## Status

Accepted.

## Context

CI artifacts were named after `V<SoftFever_VERSION>`, so two Cosmyx builds of
the same upstream base had the same name and did not show the Cosmyx patch.

## Decision

- `scripts/cosmyx/cosmyx_version.py` (standard library only) reads
  `SoftFever_VERSION` from `version.inc` and the patch from
  `src/slic3r/GUI/Cosmyx/logic/CosmyxVersion.hpp`, the same sources the app
  is built from, and gives the display version and the build tag
  `<display version>_<short hash>`, for example `2.6.0-dev-8_aa9dac8`.
- The short hash is the one `src/slic3r/GitCommitHash.cmake` embeds: the
  `git_commit_hash` variable shortened by git when it is set (pull requests),
  otherwise `git log -1 --format=%h`.
- One step in `.github/workflows/build_orca.yml`, right after the two upstream
  "Get the version and date" steps, runs `cosmyx_version.py github-env`, which
  appends `ver=<build tag>` to `GITHUB_ENV`. The later value wins, so every
  file and artifact the workflow names after `env.ver` (DMG, portable zip,
  PDB archive, MSIX, AppImage, validator, artifacts) carries the build tag.
  The step uses `shell: python`, which GitHub provides on every runner OS.
- Pull request builds get the build tag too, instead of `PR-<number>`.

## Consequences

- One upstream hook: a step between two old steps. `ver_pure` and the CMake
  installer name (`OrcaSlicer_Windows_Installer_V<SoftFever_VERSION>`) are not
  changed; the installer artifact is uploaded with a glob and named after
  `env.ver`.
- The Flatpak build (`build_flatpak.yml`) computes its own `ver` and is not
  renamed.
- Removing it: delete the step; the names go back to `V<SoftFever_VERSION>`.
