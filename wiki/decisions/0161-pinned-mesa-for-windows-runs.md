# 0161. Pinned Mesa software OpenGL for the Windows runs

## Status

Accepted.

## Context

The Windows launcher (`OrcaSlicer_app_msvc.cpp`) loads
`<exe folder>/mesa/opengl32.dll` when the system OpenGL is older than 2.0 or
`--sw-renderer` is given. The build does not ship that file, and hosted
Windows runners have no GPU, so the app has no usable OpenGL there. The user
approved downloading a pinned third-party Mesa build for tests only.

## Decision

- Source: one release of [mesa-dist-win](https://github.com/pal1000/mesa-dist-win)
  (MIT licence), the `mesa3d-<version>-release-msvc.7z` asset, pinned in
  `data/expectations.json` (`mesa_win`) with the archive's SHA-256 and size and
  the SHA-256 of each file taken.
- Pinned: 26.2.5, archive SHA-256
  `997123ef4ce8896204ab912d5b54f19372c487ff9835bcefafa2fca23b8953c2`. Newer
  releases were not taken: 26.2.6 and 26.2.7 have an MSVC build regression and
  26.2.6 ships no `opengl32.dll`; 26.3.0 was published the day this was
  written. A pin is moved only to a release at least two weeks old.
- Files: `x64/opengl32.dll`, `x64/libgallium_wgl.dll` (the driver it loads)
  and `x64/dxil.dll`, unpacked with 7-Zip `e` (Python cannot read 7z; 7-Zip is
  preinstalled on the runner and already required by 0143), each hash checked,
  copied into `mesa/` of the temporary copy of the portable folder. The app
  runs with that folder first on `PATH` (the loader looks for
  `libgallium_wgl.dll` there, not next to `opengl32.dll`) and
  `GALLIUM_DRIVER=llvmpipe`, so the CPU renderer is always the one used.
- Failures: a hash mismatch, a 7-Zip error or a download that fails three
  times fails the smoke and slice records; a missing 7-Zip skips them with that
  reason (a failure in strict mode).
- The archive is cached between runs with `actions/cache`, keyed on
  `data/expectations.json`; the hash is checked whatever the cache returns.
- Test-only: Mesa never goes into an artifact, the repository or the build.
- OS exception: Mesa exists for Windows only, behind `mesa_win.py`.

## Consequences

- The Windows job downloads about 70 MB from GitHub when the cache is cold.
- A deleted or re-uploaded release asset fails the Windows runs until the pin
  is moved (wiki/cosmyx/artifact-checks.md, "Updating the Mesa pin").
- Removing it means dropping `mesa_win.py`, the `mesa_win` pin and the cache
  step; the Windows smoke and slice of 0160 would then have no OpenGL.
