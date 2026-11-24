# ci/cosmyx-artifact-checks (PR #100)

## Purpose

A green "Build all" only says the steps ran. This feature inspects what a finished "Build all" run produced, on the OS each artifact is for, and posts the commit status `cosmyx/artifact-checks` on the built commit (JUnit report, Markdown summary, merged records):

- Windows: every PE file (found by magic bytes) in the portable folder, the NSIS installer payload (7-Zip 23.01+), the uninstaller, the profile validator and MSIX files; Authenticode signatures (`signtool verify /pa /all /tw`), ours vs allowlisted vendor files; portable vs installer payload hash equality.
- macOS: every DMG mounted read-only; exact `lipo -archs` per family; valid arm64 signature; app signature class reported.
- Linux: AppImage unpacked, ELF machine check, `AppRun --help` under xvfb, a slice of the shipped `cosmyx_cube.3mf` whose G-code must have the header, config block, feature types and at least 100 `G1` moves.
- Every OS: artifact names carry `<display version>_<short hash>`, shipped translations match the Cosmyx catalogues, shipped models equal `resources/cosmyx/`, required artifacts exist on DEV and `release/*` builds.
- Modes `enforce` / `not-configured` / `report` follow the signing predicate (decision 0098: Azure secrets set, DEV or `release/*`, not PR, not MIXED). Untrusted-input rules (decision 0141): scripts always come from the workflow's own commit, fork builds are never executed, artifact names and tool output are escaped.

## Parent and dependencies

Parent: `DEV` (carries the foundation commits; own commits `06277d6620`, `ef2e1158fe`, `6606049817`, `0f41654edd`, `0f40efe642`, plus the foundation's `92830e0a8b` which only this and later branches contain). Decisions 0140-0149.

It reads, but does not own, the following from other branches or from upstream:
- Upstream workflow name `Build all` (`workflow_run` trigger `workflows: ["Build all"]`) and the artifact names its `build_orca.yml` uploads: `OrcaSlicer_Windows_<ver>[_arm64][_msvc][_portable]`, `OrcaSlicer_Windows_MSIX_...`, `OrcaSlicer_profile_validator_Windows_<ver>`, `OrcaSlicer_Mac_bundle_<arch>_<sha>`, `OrcaSlicer_Mac_universal_<ver>`, `OrcaSlicer_Mac_<arch>_<ver>`, `OrcaSlicer_profile_validator_Mac_universal_DMG_<ver>`, `OrcaSlicer_Linux_ubuntu_<ver>[_aarch64]_<ver>`, `OrcaSlicer_profile_validator_Linux_ubuntu_<ver>_<ver>`, test assets `<sha>-tests-*`. The regexes live in `scripts/cosmyx/artifact_checks/data/expectations.json`.
- Data files of the built commit supplied by other Cosmyx tasks: `version.inc`, `CosmyxVersion.hpp` (T5/T6), `localization/cosmyx/` (T8), `resources/cosmyx/` including `models/cosmyx_cube.3mf`. A check whose source is not merged is skipped with a message.
- Repository secrets (Azure: six `AZURE_*`; presence only) and variables `COSMYX_SIGN_ALL_REFS`, optional `COSMYX_SIGN_EKU`, `COSMYX_SIGN_SUBJECT`.
- Runner tools: 7-Zip, `signtool`, `lipo`, `codesign`, `unsquashfs`, `xvfb-run`.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `.github/workflows/cosmyx-artifact-checks.yml` | CI (Cosmyx-owned) | `workflow_run` on "Build all" plus `workflow_dispatch` (`run_id`, `strict`); jobs `resolve`, `check` (matrix windows-latest, macos-15, ubuntu-24.04), `report`, `status`. |
| `scripts/cosmyx/artifact_checks/{__init__,cli,inventory,signing_policy,allowlist,binfmt,policy_windows,macos,linux,slice,content,records,report}.py`, `facts_windows.ps1` | Cosmyx-owned | CLI subcommands `resolve`, `windows`, `macos`, `linux`, `content`, `report`, `download`, `local`. |
| `scripts/cosmyx/artifact_checks/data/expectations.json`, `data/allowlist.json` | data | Artifact family regexes, required set, timeouts; the vendor allowlist ships empty. |
| `scripts/cosmyx/just/tests.just` | Cosmyx-owned | Recipes `artifact-checks`, `artifact-checks-status`, `artifact-checks-local` (imported by the foundation justfile). |
| `scripts/cosmyx/tests/test_artifact_checks_{allowlist,binfmt,content,inventory,linux,macos,report,signing_policy,slice,windows}.py`, `artifact_checks_windows.Tests.ps1`, `test_breaker_{export_subject,msix_badzip,report_junit,report_markdown,smoke_output_encoding}.py`, `undecodable_output.py` | test | Unit tests (the Pester file runs on the Windows leg), breaker tests pin each security hole. |
| `wiki/cosmyx/artifact-checks.md`, `wiki/decisions/0140-0149` | docs | Design and decisions. |
| `CHANGELOG.md` | docs | One line under the T13 slot. |
| `.github/workflows/cosmyx-checks.yml`, `tests/CMakeLists.txt` | shared | Foundation copies; `tests/CMakeLists.txt` carries the foundation hook `add_subdirectory(cosmyx) # Cosmyx`. |

No upstream file is edited by this branch's own commits.

## Rebase risk zones

The feature has no code hook; its risk is the coupling to upstream's build output and workflow names.

| Coupling | DEV vs v2.5.1 | Churn |
|---|---|---|
| Workflow name `Build all` in `build_all.yml` | Same name in both. `build_all.yml` itself changed a lot (316 lines). | high |
| `build_orca.yml` artifact names | Identical names for macOS universal DMG, validator DMGs, Windows portable/installer/validator/MSIX, Linux AppImage. Differences: DEV adds a per-arch DMG upload `OrcaSlicer_Mac_<arch>_<ver>` (line ~246) that the tag lacks; DEV names the PDB artifact `PDB${{ inputs.compiler != 'clang' && '_msvc' || '' }}` where the tag has plain `PDB`. The expectations regexes for `mac-arm64`/`mac-x86_64` match nothing on the tag (harmless) but a changed name on a newer tag silently drops a family:. | `build_orca.yml`: 20 commits since 2026-01 |
| Required set | The tag has no `arm64`/`msvc` build matrix differences that matter; `required.branches` is `^DEV$`, `^release/`: a rebased release branch named `release/*` is covered. | |
| Resources and data the checks read | `resources/cosmyx/`, `localization/cosmyx/`, `version.inc` must come from the other rebased branches; on the tag, upstream's own `version.inc` format may differ (check `content.py` version parsing). | |

## Intent to preserve

- After every Build all run, each artifact family is checked on its own OS, the commit status `cosmyx/artifact-checks` is posted, and failures are never swallowed: unknown artifact names are reported, not ignored.
- Trust boundary: check scripts come from this workflow's own commit; the built commit provides data files only; fork builds are never executed; all artifact names and tool output are treated as untrusted.
- If upstream renames or restructures artifacts (new tag), update `data/expectations.json` regexes and the matching tests rather than loosening the checks. If upstream renames the "Build all" workflow, change the `workflows:` trigger and the `just` recipes' workflow name.

## Verification

- `just test-scripts`: all `test_artifact_checks_*` modules (windows 26, macos 17, report 16, inventory 13, linux 10, content 10, slice 10, binfmt 11, signing_policy 7, allowlist 6), the `test_breaker_*` modules, `test_foundation.py`, and `artifact_checks_windows.Tests.ps1` on Windows (`COSMYX_REQUIRE_PESTER=1`).
- `just artifact-checks-local <run id>` against a finished Build all run of the rebased branch on each OS; `just artifact-checks <run id>` in CI; check the `cosmyx/artifact-checks` status and the `cosmyx-artifact-checks-report` artifact.
- A real DEV run needs the allowlist filled after the first signed run (see `wiki/cosmyx/artifact-checks.md`).

## Known pitfalls

- 0f40efe642: `linux.py` built its crash set from the host `signal` module. Windows has no `signal.SIGBUS` (import error on the Windows runner), macOS numbers SIGBUS 10. The table now holds fixed Linux numbers; a test also pinned `shutil.which` (ubuntu runners have `unsquashfs`).
- 0f41654edd: artifact paths and tool output are attacker-controlled: a newline in a file name could forge a "Result: passed" line, control characters broke `junit.xml`, undecodable bytes raised `UnicodeDecodeError`, a damaged MSIX raised `BadZipFile`, and `git ls-tree` without `-z` exported non-ASCII model names as empty files.
- Paths and line endings: files under `scripts/cosmyx/artifact_checks/` are read on three OSes; keep LF and avoid host-specific separators.
- 92830e0a8b: the checks workflow `paths:` must cover the files this feature owns.
- `53df024c32` (package-name follow-up, decision 0148 edited): every artifact family pattern, the names check (new `name_prefixes` list) and the Windows own names accept both `OrcaSlicer_*` and `CosmoSlice_*`, and `CosmoSlice.exe` as well as `orca-slicer.exe`; the profile validator families are optional (product-name decision 0211 stops exporting them). Children (macos-signing, exec-smoke) were restacked on it, so their shas changed.

## Shared files with other branches

`CHANGELOG.md` (T13 slot, decisions 0140-0149), `justfile`, `scripts/cosmyx/just/tests.just` (also expected by the T13 test CI), `scripts/cosmyx/run_script_tests.py`, `scripts/cosmyx/decisions.py`, `scripts/cosmyx/tests/test_foundation.py` (198-line variant here), `.github/workflows/cosmyx-checks.yml`, `wiki/decisions/0001-0005` and `README.md`, `tests/CMakeLists.txt`, `wiki/cosmyx/artifact-checks.md` (edited again by `ci/cosmyx-macos-signing` and `ci/cosmyx-exec-smoke`), `scripts/cosmyx/artifact_checks/{cli,macos,records,report,signing_policy,linux,slice}.py`, `data/expectations.json`, `.github/workflows/cosmyx-artifact-checks.yml` and `scripts/cosmyx/tests/test_breaker_*.py` (all edited by the two stacked children). Rebase order: foundation, this branch, `ci/cosmyx-macos-signing`, `ci/cosmyx-exec-smoke`.
