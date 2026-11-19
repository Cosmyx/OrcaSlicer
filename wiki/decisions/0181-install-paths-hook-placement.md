# 0181. Hook placement for the install and data folder change

## Status

Accepted.

## Context

Decision 0002 puts a Cosmyx include right after an upstream file's first
include. In `src/slic3r/GUI/GUI_App.cpp`, lines 2, 3 and 4 are already taken
by other Cosmyx branches (version and dark mode, the logs, the GUI goldens);
stacking a fourth include there makes every pair of those branches touch the
same lines.

## Decision

- `src/slic3r/GUI/GUI_App.cpp`:
  - after `#include "Downloader.hpp"`, the last quoted include of the first
    block: `#include "Cosmyx/AppPaths.hpp" // Cosmyx`;
  - right after `SetAppName(SLIC3R_APP_KEY);` in `init_app_config()`:
    `Cosmyx::use_vendor_data_dir(); // Cosmyx`;
  - in `migrate_flatpak_legacy_datadir()`, the line that copies the data folder
    path now goes through `::Slic3r::Cosmyx::without_vendor_dir()`;
  - in `check_old_linux_datadir()`, the default path goes through
    `::Slic3r::Cosmyx::vendor_app_subdir()`.
  The libslic3r helpers are called fully qualified, because inside
  `Slic3r::GUI` the name `Cosmyx` finds `Slic3r::GUI::Cosmyx` first.
- `src/libslic3r/utils.cpp`: line 2 `#include "Cosmyx/DataDir.hpp" // Cosmyx`
  (no other Cosmyx branch edits this file), and the last line of
  `default_data_dir()`.
- `CMakeLists.txt` (top level): `include(cmake/cosmyx/Packaging.cmake) # Cosmyx`
  right before `include(CPack)`, after every upstream `CPACK_*` value. The
  CMake and NSIS files live in `cmake/cosmyx/`, an Orca folder with a Cosmyx
  subfolder.
- The call after `SetAppName` leaves the commented `SetAppDisplayName` line
  untouched, since the product-name branding patches that exact line.

## Consequences

- Six one-line edits in `GUI_App.cpp` and `utils.cpp` (three of them change an
  upstream line) and one in `CMakeLists.txt`; `git grep Cosmyx` lists them.
- Removing it: delete the added lines and restore the three changed upstream
  lines.
