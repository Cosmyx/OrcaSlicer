# 0060. Display version format

## Status

Accepted.

## Context

Users and support need to tell one Cosmyx build from another, and from the
OrcaSlicer release it is based on. The first plan showed a separate
"Cosmyx Bundle Version" line in the About dialog; the user chose one version
string instead.

## Decision

- The version shown to the user is `<SoftFever_VERSION>-<Cosmyx patch>`, for
  example `2.6.0-8`.
- The Cosmyx patch is an integer that starts at 8 and is raised by hand for
  each Cosmyx build that is handed out. It never goes down; the C++ test and
  the script refuse a value below 8.
- `SoftFever_VERSION` itself is not changed. Project files (3MF), presets, the
  updater and the upstream bug report link parse it as an OrcaSlicer semver,
  and changing it would also mean editing `version.inc` on every upstream
  merge.

## Consequences

- No new translatable string: the About dialog keeps its single version label.
- Removing it: drop `src/slic3r/GUI/Cosmyx/logic/CosmyxVersion.{hpp,cpp}`, the
  hook lines listed in decision 0063, the build workflow step of decision 0062
  and their tests.
