# ci/cosmyx-exec-smoke (PR #104)

## Purpose

Extends the artifact checks from Linux-only runs to Windows and macOS. After every "Build all" run, the Windows x64 portable app and the macOS app inside the mounted DMG are launched (`--help`, 60 s) and slice the shipped cube model (`resources/cosmyx/models/cosmyx_cube.3mf`, 300 s), judged on the G-code they write exactly as on Linux. A Windows or macOS app that crashes at start or cannot slice no longer passes. On Windows the app runs from a temporary copy with a pinned, hash-checked Mesa software OpenGL (mesa-dist-win 26.2.5, MIT, test-only, never shipped), because runners have no GPU. Crashes are named from NTSTATUS (Windows) or the Darwin signal numbers (macOS). `mesa_win.fetch` is also exposed for the GUI goldens launcher, which shares the one pin and integrity check.

## Parent and dependencies

Parent: `ci/cosmyx-macos-signing` (#105), hence also #100 and the foundation #86; own commits `b5191c2caa`, `fc3a54ec72`, `a78bba4c6f`, `449d09ffa9`, `4492bceec5`, `3aa8f5ac9b`, `fcf2a4cc91`; decisions 0160 and 0161. Depends on: the built app (`orca-slicer.exe`, the macOS bundle's `Contents/Info.plist` `CFBundleExecutable` and `Contents/MacOS`), upstream's command-line options (`--help`, slicing a `.3mf`; `--sw-renderer` is rejected by the parser and must never be passed), `resources/cosmyx/models/cosmyx_cube.3mf` (another branch), `slice.py` from the parent, the pinned Mesa archive from github.com/pal1000/mesa-dist-win.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `scripts/cosmyx/artifact_checks/smoke_native.py` | Cosmyx-owned | Runs apps from a temporary copy, `app_executable()` (plain file name resolving inside `Contents/MacOS`, else bundle name; refuses symlinks out of the bundle), smoke and slice, Windows NTSTATUS and Darwin signal tables. |
| `scripts/cosmyx/artifact_checks/mesa_win.py` | Cosmyx-owned | Downloads the Mesa 7z, checks size and SHA-256 of the archive and of `opengl32.dll`, `libgallium_wgl.dll`, `dxil.dll`; `prepare()` places them in `<app>/mesa` and next to the exe; `fetch()` for the goldens launcher; sets `GALLIUM_DRIVER=llvmpipe`. |
| `scripts/cosmyx/artifact_checks/{cli,linux,macos,slice}.py`, `data/expectations.json` | Cosmyx-owned | Calls the native smoke on windows and macos; the `mesa_win`, `windows.run_archs`, `smoke_timeout`, `slice_timeout` entries. |
| `.github/workflows/cosmyx-artifact-checks.yml` | CI | `actions/cache@v6` step for the Mesa archive keyed on the hash of `expectations.json` (`COSMYX_MESA_CACHE`), timeout raised. |
| `scripts/cosmyx/tests/test_artifact_checks_smoke_native.py`, `test_artifact_checks_mesa_win.py`, edits to `test_breaker_info_plist.py`, `test_breaker_smoke_output_encoding.py`, `test_foundation.py` | test | 22 + 11 new tests; breaker tests complete. |
| `wiki/cosmyx/artifact-checks.md`, `wiki/decisions/0160`, `0161`, `0003` | docs | Updated design, new decisions. |
| `CHANGELOG.md` | docs | Line under T13. |

No upstream file is edited by this branch.

## Rebase risk zones

No upstream hook. The coupling is to upstream's runtime behaviour: v2.5.1 versus DEV has no check here, so on the new tag re-verify that `orca-slicer.exe --help` and the slice command-line (exact flags are in `slice.py`) behave the same (CLI option parsing lives in `src/OrcaSlicer.cpp`, high churn), that the macOS bundle executable is still named in `CFBundleExecutable`, and that the Windows launcher still checks `opengl32.dll` by name (the reason Mesa is placed next to the exe). The pinned Mesa download URL, version and hashes must stay valid (no network in tests; the integrity check is the guard).

## Intent to preserve

- After every build, Windows x64 and macOS apps are really run and must slice the shipped cube to valid G-code; Mesa is test-only, hash-pinned, never shipped, never trusted on its own cache.
- A macOS executable outside its bundle is never run; child output is decoded with replacement characters.
- If upstream changes the CLI (renamed flags, mandatory arguments), adapt `slice.py` and `smoke_native.py` command lines and tests, not the pass criteria (header, config block, feature types, at least 100 `G1` moves).

## Verification

- `just test-scripts`: `test_artifact_checks_smoke_native.py` (22), `test_artifact_checks_mesa_win.py` (11), `test_breaker_info_plist.py`, `test_breaker_smoke_output_encoding.py`, and all parent tests.
- CI: run Build all on the rebased branch, then `just artifact-checks <run id>`; the Windows and macOS legs must report smoke and slice records as passed (not skipped) in `report.md`.
- Manually on Windows: extract the portable zip, run `just artifact-checks-local <run id>`.

## Known pitfalls

- 3aa8f5ac9b: `CFBundleExecutable` from the artifact's Info.plist was joined unvalidated (`../../../tmp/x` ran a file outside the app), non-dict plist roots raised `AttributeError`, non-string names `TypeError`, and strict decoding raised `UnicodeDecodeError`.
- fcf2a4cc91: the macOS run reused the Linux crash table; Darwin numbers SIGBUS 10 (Linux 7), and tests using the host `signal` module gave wrong numbers on the Windows runner. Tables are fixed per target OS.
- 4492bceec5: the launcher loads `opengl32.dll` by name and searches the exe folder first, so Mesa must also sit next to the exe; `--sw-renderer` is rejected by the command line parser.
- 449d09ffa9: `mesa_win.fetch` is a public contract with the goldens launcher; do not rename.
- Restacked on the new macos-signing: tip `526fc8002e`. That commit makes `windows.app_exe` an ordered list `["CosmoSlice.exe", "orca-slicer.exe"]`: the smoke and slice run the first name present in the portable folder, and fail listing both when neither is there; tests cover the renamed `CosmoSlice.app` on macOS.

## Shared files with other branches

`CHANGELOG.md`, `wiki/cosmyx/artifact-checks.md`, `wiki/decisions/0003-changelog-slots.md`, `.github/workflows/cosmyx-artifact-checks.yml`, `scripts/cosmyx/artifact_checks/{cli,macos,linux,slice}.py` and `data/expectations.json` (all also edited by `ci/cosmyx-artifact-checks` and `ci/cosmyx-macos-signing`), `scripts/cosmyx/tests/test_foundation.py`, `scripts/cosmyx/tests/test_breaker_info_plist.py`, `test_breaker_smoke_output_encoding.py`. `mesa_win.fetch` is also consumed by the GUI goldens branch (`scripts/cosmyx/just/goldens.just`, not in this set). Rebase last in the stack.
