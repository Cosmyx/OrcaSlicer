# 0160. Smoke run and slice on Windows and macOS

## Status

Accepted. Completes 0147, which deferred these runs.

## Context

Until now only the Linux x64 AppImage was run (0147). A Windows or macOS build
that links, signs and packs but crashes at start or cannot slice passed every
check.

## Decision

- When the build may be run (0141), the Windows and macOS jobs run the same two
  checks as Linux, through `smoke_native.py`:
  - `<app> --help` within 60 s: a hang or a crash fails, a nonzero exit passes
    only after a usage text;
  - the slice of the shipped `cosmyx/models/cosmyx_cube.3mf` within 300 s,
    with `--datadir <tmp> --outputdir <tmp> --slice 0`, judged by `slice.py`
    on `result.json` and `plate_*.gcode` exactly as on Linux.
- macOS: from the read-only mounted image, the executable named by the app's
  `Info.plist` (`CFBundleExecutable`). Only images whose architectures include
  the runner's are run; the others are skipped by design.
- Windows: `orca-slicer.exe` of a temporary copy of each x64 portable folder
  (the downloaded artifact is never changed), with the pinned Mesa of 0161.
  arm64 folders are skipped by design. `--sw-renderer` is not passed: the
  command line parser of the app does not know it, and the launcher already
  loads Mesa when the default OpenGL is older than 2.0, which is the case on
  the GPU-less hosted runner.
- Crashes are named in the record: the signal on macOS, the NTSTATUS of the
  exit code on Windows (`STATUS_ACCESS_VIOLATION`, `STATUS_DLL_NOT_FOUND`...).
- Limits live in `data/expectations.json` (`windows`, `macos`), so they can be
  tuned without code.
- The OS-specific parts (how the app is found, Mesa) stay behind
  `smoke_native.py` and `mesa_win.py`; the rules are the shared ones of
  `linux.smoke_status` and `slice.py` (0142).

## Consequences

- The check job takes a few more minutes per OS; its limit goes from 60 to 90
  minutes.
- A slice that needs a GPU-specific feature on Windows would show here first.
- Removing this means dropping `smoke_native.py`, `mesa_win.py`, their calls in
  `cli.py` and `macos.py`, the Mesa cache step and the `windows`, `macos` and
  `mesa_win` limits, then superseding this decision.
