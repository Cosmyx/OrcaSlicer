# 0002. Upstream hook placement

## Status

Accepted.

## Context

Cosmyx code must be reached from upstream files (CMake targets, the print
config definition, G-code generation). Every edited upstream line is a
possible merge conflict.

## Decision

- An upstream file gets at most a few one-line hooks: one include, one call,
  one `include()` or `add_subdirectory()`.
- A Cosmyx include goes right after the file's first include (line 1), which
  upstream almost never edits.
- A call goes next to old, stable lines.
- Every hook line ends with `// Cosmyx` (C++) or `# Cosmyx` (CMake), so
  `git grep Cosmyx` lists them all.
- The foundation hooks are:
  - `src/libslic3r/CMakeLists.txt`, after `source_group(...)` of libslic3r:
    `include(Cosmyx/Cosmyx.cmake) # Cosmyx`
  - `src/slic3r/CMakeLists.txt`, after `source_group(...)` of libslic3r_gui and
    before `encoding_check()` and the precompiled header:
    `include(GUI/Cosmyx/Cosmyx.cmake) # Cosmyx`
  - `tests/CMakeLists.txt`, between `slic3rutils` and `fff_print`:
    `add_subdirectory(cosmyx) # Cosmyx`
  - `src/libslic3r/PrintConfig.cpp`, line 2:
    `#include "Cosmyx/ConfigDefExtensions.hpp" // Cosmyx`
  - `src/libslic3r/PrintConfig.cpp`, in `PrintConfigDef::PrintConfigDef()`
    between `init_extruder_option_keys()` and the `ptFFF` tagging, so Cosmyx
    options are FFF options: `Cosmyx::extend_print_config_def(*this); // Cosmyx`
  - `src/libslic3r/GCode.cpp`, line 2:
    `#include "Cosmyx/GCodeHooks.hpp" // Cosmyx`
- GCode.cpp gets no other include: `GCodeHooks.hpp` includes the feature
  headers.

## Consequences

- The scheduled MIXED branch (DEV merged with upstream) proves the hooks still
  apply cleanly; a conflict there is a bug in a hook.
- Removing a hook means deleting its single line.
