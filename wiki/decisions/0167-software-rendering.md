# 0167. Software OpenGL where the OS allows it

## Status

Accepted.

## Context

GPU drivers differ between runners and change with runner images; a software
renderer gives stable 3D pixels.

## Decision

- Linux: Mesa llvmpipe from the pinned image; the harness records
  `GL_RENDERER` in `environment.json`.
- Windows: the harness fetches the pinned mesa-dist-win build into the
  portable copy's `mesa/` folder with `artifact_checks.mesa_win.fetch()` and
  starts the app with `mesa_win.run_env()` (T16a, decision 0161), imported at
  run time from the trusted checkout. The Mesa DLLs are also copied next to
  the executable: `opengl32.dll` is not a known DLL, so that copy wins over
  the system driver. The launcher's `--sw-renderer` switch is not used: the
  launcher passes it on to the command line parser, which rejects it (the
  option is commented out in `PrintConfig.cpp`).
- macOS: there is no software switch; the runner's renderer is used and the
  pixel tolerance of decision 0168 absorbs its noise (OS exception).

## Consequences

- A renderer change shows up as drift in `environment.json` before it shows
  up as failed goldens.
