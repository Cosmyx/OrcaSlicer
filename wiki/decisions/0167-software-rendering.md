# 0167. Software OpenGL where the OS allows it

## Status

Accepted.

## Context

GPU drivers differ between runners and change with runner images; a software
renderer gives stable 3D pixels.

## Decision

- Linux: Mesa llvmpipe from the pinned image; the harness records
  `GL_RENDERER` in `environment.json`.
- Windows: the portable build runs with `--sw-renderer`, which loads
  `<exe>/mesa/opengl32.dll`; the harness puts the pinned mesa-dist-win build
  there with `artifact_checks.mesa_win.fetch(dest_dir)` (T16a, decision 0161),
  imported at run time from the trusted checkout.
- macOS: there is no software switch; the runner's renderer is used and the
  pixel tolerance of decision 0168 absorbs its noise (OS exception).

## Consequences

- A renderer change shows up as drift in `environment.json` before it shows
  up as failed goldens.
