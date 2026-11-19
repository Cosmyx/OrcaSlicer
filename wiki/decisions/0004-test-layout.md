# 0004. Test layout

## Status

Accepted.

## Context

Every Cosmyx change ships with its tests. The upstream unit test job runs
everything ctest discovers, and its workflow is an upstream file.

## Decision

- C++ tests live in `tests/cosmyx/`, built as `cosmyx_tests` and discovered by
  ctest like the upstream suites, so the existing unit test job runs them
  without any workflow change.
- The suite globs `test_*.cpp` and `src/slic3r/GUI/Cosmyx/logic/*.cpp`, reuses
  the print fixtures of `tests/fff_print/test_helpers.cpp`, links
  `test_common`, `libslic3r` and Catch2, and uses the libslic3r precompiled
  header like `fff_print`. Every test case carries the `[cosmyx]` tag.
- Tooling scripts are tested in `scripts/cosmyx/tests/`: `test_*.py` with the
  Python standard library `unittest`, and `*.Tests.ps1` with Pester for
  PowerShell scripts. `just test-scripts` runs both and skips Pester with a
  message when PowerShell is not installed.
- The Cosmyx checks workflow runs `just test-scripts` on Linux, macOS and
  Windows; Pester is guaranteed on Windows runners.

## Consequences

- No local build is needed to add a test; CI compiles and runs it.
- Removing the suite means deleting `tests/cosmyx/` and its
  `add_subdirectory` hook.
