# 0001. Cosmyx module layout and globbing

## Status

Accepted.

## Context

The fork must merge upstream OrcaSlicer with zero conflicts. Any line Cosmyx
adds to an upstream source list or CMake file is a line upstream may also edit.
Several features are developed in parallel and must not edit the same files.

## Decision

- Core code lives in `src/libslic3r/Cosmyx/` (namespace `Slic3r::Cosmyx`), GUI
  code in `src/slic3r/GUI/Cosmyx/` (namespace `Slic3r::GUI::Cosmyx`).
- GUI logic that needs no wxWidgets lives in `src/slic3r/GUI/Cosmyx/logic/`, so
  the test suite can compile it without the GUI library.
- Each module folder has one `Cosmyx.cmake` that globs its sources with
  `file(GLOB CONFIGURE_DEPENDS ...)` and adds them to the existing target with
  `target_sources(... PRIVATE ...)`, using absolute paths from
  `CMAKE_CURRENT_LIST_DIR`. Objective-C++ files in the GUI module skip the
  precompiled header.
- A feature adds files to these folders; it never edits a CMake file.
- Print options go through one seam, `ConfigDefExtensions.{hpp,cpp}`: a
  dispatcher calls one extender per feature, each defined in the feature's own
  file. `ConfigDef::add()` is protected, so options are defined with
  `Cosmyx::add_option()`, which numbers them from 2^30 upward so their
  serialization ordinals never collide with upstream ones.

## Consequences

- CMake re-globs when files are added or removed; a fresh configure is never
  needed by hand.
- Removing Cosmyx means deleting the two Cosmyx folders and the hook lines of
  decision 0002.
