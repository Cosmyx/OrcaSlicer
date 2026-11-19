# 0185. Upstream's default data folder test follows the Cosmyx folder

## Status

Accepted. Amends 0181.

## Context

Decision 0180 moves the Linux data folder to `$XDG_CONFIG_HOME/Cosmyx/OrcaSlicer`.
Upstream's test "default_data_dir is the XDG config dir without a portable
data_dir folder" (`tests/libslic3r/test_utils.cpp`, Linux only) expects
`$XDG_CONFIG_HOME/OrcaSlicer`, so it fails on every Cosmyx build.

Rules forbid loosening or deleting a test, and upstream files take only the
smallest hook. Writing the expected path as a literal (`"Cosmyx/"
SLIC3R_APP_KEY`) would duplicate the vendor name in a second place. The user
chose a one-line hook that builds the expected value with
`Cosmyx::vendor_app_subdir()`, the same helper `default_data_dir()` uses.

No other upstream test asserts the data folder location: `xdg_config_dir()`
keeps upstream behaviour and its own test passes, Windows and macOS take the
folder from `wxStandardPaths` in the GUI with no upstream test, and the plugin
audit tests only build paths under `data_dir()`.

## Decision

- `tests/libslic3r/test_utils.cpp`, an upstream test file, gets two lines
  tagged `// Cosmyx`, an exception to keeping upstream files untouched outside
  `src/`:
  - `#include "libslic3r/Cosmyx/DataDir.hpp" // Cosmyx`, right after
    `#include "libslic3r/Utils.hpp"`;
  - the expected value of that test becomes
    `"/tmp/xdg-test/" + Slic3r::Cosmyx::vendor_app_subdir(SLIC3R_APP_KEY)`.
- The test still checks the whole path, so it still catches a portable
  `data_dir` folder or a wrong XDG base.
- `scripts/cosmyx/tests/test_install_paths.py` pins both lines.

## Consequences

- Two lines in an upstream test file; `git grep Cosmyx tests/libslic3r` lists
  them. If upstream edits that test, the merge conflicts on the hooked line
  only.
- Removing it: delete the include and restore the upstream expected value,
  together with reverting 0180.
