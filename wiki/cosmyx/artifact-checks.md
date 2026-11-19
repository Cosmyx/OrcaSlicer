# Artifact checks

After every "Build all" run, the workflow `cosmyx-artifact-checks.yml` downloads
what the build produced and checks it on the OS it is meant for: signatures,
installer payload, architectures, ELF files, a smoke run and a slice on every
OS, the build tag in the names, the shipped translations and models. The result
is a JUnit report, a Markdown summary on the run page, and the commit status
`cosmyx/artifact-checks` on the built commit. Decisions 0140 to 0149, 0156 for
the macOS Developer ID rules, and 0160 and 0161 for the Windows and macOS runs.

## How it runs

| Job | Runner | What it does |
|-----|--------|--------------|
| resolve | ubuntu-24.04 | Reads the build run and its artifacts, picks the mode, checks the required set, posts the `pending` status. Skips cancelled and skipped builds. |
| check (matrix) | windows-latest, macos-15, ubuntu-24.04 | One leg per OS that has artifacts: downloads them, runs `cli.py <os>` and `cli.py content`, uploads `cosmyx-checksums-<os>-<tag>` (records, `SHA256SUMS`, `manifest.json`, 30 days). |
| report | ubuntu-24.04 | Merges the records into `junit.xml` and `report.md` (artifact `cosmyx-artifact-checks-report`), writes the step summary, fails on any failure. |
| status | ubuntu-24.04 | Posts `success` or `failure` on the built commit. |

The scripts and the allowlist always come from the workflow's own commit; the
built commit only provides data files (`version.inc`, `CosmyxVersion.hpp`,
`localization/cosmyx/`, `resources/cosmyx/`). Builds from forks are never
executed (decision 0141).

The code lives in `scripts/cosmyx/artifact_checks/`: `cli.py` (entry point),
`inventory.py` (artifact families, required set, names), `signing_policy.py`
(modes), `allowlist.py`, `policy_windows.py` with `facts_windows.ps1`,
`macos.py`, `linux.py`, `slice.py`, `smoke_native.py` (Windows and macOS runs),
`mesa_win.py` (pinned Mesa for Windows), `content.py`, `report.py`. Artifact
name patterns, limits and the Mesa pin are in `data/expectations.json`.

## What is checked

### Windows

- Every PE file, found by its magic bytes, in the portable folders, the NSIS
  installer and its payload (7-Zip 23.01 or newer), the uninstaller a silent
  install writes (x64 only), the profile validator when the build still
  exports it, and the MSIX package's files. The MSIX package itself is unsigned by design.
- Signatures (decision 0143): `signtool verify /pa /all /tw /v` exit 0, status
  `Valid`, and each file ours and timestamped, or a vendor file in the
  allowlist, or an unsigned file allowed by an `unsigned-ok` entry.
  Ours: the Artifact Signing EKU `1.3.6.1.4.1.311.97.1.0` and code signing,
  plus the optional pins `COSMYX_SIGN_EKU` and `COSMYX_SIGN_SUBJECT`.
- Payload: every PE of the portable folder is in the installer payload with
  the same SHA-256 (every mode).
- Smoke and slice (x64 portable, when the build may be run, decision 0160):
  the portable folder is copied to a temporary folder, the pinned Mesa
  software OpenGL goes into its `mesa/` folder (below), then
  `orca-slicer.exe --help` (60 s) and the slice of the shipped cube (300 s),
  judged like on Linux. A crash is named from its NTSTATUS exit code
  (`STATUS_ACCESS_VIOLATION`, for example). arm64 folders are not run.
- Mesa (decision 0161): the hosted runner has no GPU, so the app's launcher
  loads `<exe folder>/mesa/opengl32.dll`, which the build does not ship. The
  check downloads one pinned
  [mesa-dist-win](https://github.com/pal1000/mesa-dist-win) release (MIT), checks
  the archive's SHA-256, unpacks `opengl32.dll`, `libgallium_wgl.dll` and
  `dxil.dll` from its `x64/` folder with the runner's 7-Zip, checks each file's
  SHA-256, puts them in `mesa/` and next to the exe (the launcher's OpenGL
  check finds them there), and runs the app with `mesa/` first on `PATH` and
  `GALLIUM_DRIVER=llvmpipe`. `--sw-renderer` is never passed: the app rejects it. Mesa is test-only and never reaches an artifact.
  A hash mismatch or a failed download fails both runs; no 7-Zip skips them
  with that reason (a failure in strict mode). The archive is cached between
  runs (`actions/cache`, keyed on `data/expectations.json`; the hash is checked
  whatever the cache returns).

### macOS

- Every DMG (not the `Mac_bundle` tarballs) is mounted read-only; every Mach-O
  file must have exactly the family's architectures (`lipo -archs`) and a
  valid arm64 signature (`codesign --verify --strict --arch arm64`, ad-hoc is
  enough).
- Each `.app`: `codesign --verify --deep --strict` and its signature class,
  reported only: "not Developer-ID signed (expected, 0146)", unless the build
  was Developer ID signed (macOS `enforce` mode, decision 0156). Then, for the
  universal app and the profile validator DMGs: the app is Developer ID signed
  by the `TEAM_ID` team; every Mach-O file has a Developer ID authority, the
  team, the hardened runtime, a secure timestamp and no `get-task-allow`
  (`macho_identity`); the DMG is Developer ID signed by the team (`dmg_sig`);
  the DMG and its apps are stapled and Gatekeeper accepts them as notarised
  (`notarization`). The per-arch DMGs stay ad-hoc and are reported only.
- Smoke and slice (when the build may be run, decision 0160): from the mounted
  image, `<app>/Contents/MacOS/<CFBundleExecutable> --help` (60 s) and the
  slice of the shipped cube (300 s), judged like on Linux. Only disk images
  whose architectures include the runner's are run (the arm64 runner skips the
  x86_64-only image by design). A crash is named from its signal.

### Linux

- x64 AppImage: unpacked, every ELF file must be x86_64; `AppRun --help` under
  `xvfb-run` (60 s); a slice of the shipped `cosmyx_cube.3mf` (300 s) whose
  G-code has the header block, the `; generated by <app> <version> on` line,
  the config block, feature types and at least 100 `G1` moves.
- aarch64 AppImage and the profile validator (when exported): their ELF
  machine only.

### Every OS

- Names: every `OrcaSlicer_*` or `CosmoSlice_*` artifact (except
  `Mac_bundle`) carries `<display version>_<short hash of the built commit>`.
- Translations: every translated Cosmyx entry reads the same from the shipped
  `.mo` catalogue.
- Models: every file of `resources/cosmyx/` is shipped unchanged.
- Required artifacts on successful DEV and `release/*` builds: Windows x64
  portable and installer, the universal DMG (not on schedule runs), the Linux
  x64 AppImage. The profile validator artifacts are not required: Cosmyx
  builds no longer export them.

Artifact names are matched with either product prefix, `OrcaSlicer_` or
`CosmoSlice_` (same suffixes), and the app's own executables (never covered by
an `unsigned-ok` entry) are `OrcaSlicer*.exe`, `orca-slicer.exe`,
`CosmoSlice*.exe`, `CosmoSlice.exe` and `Uninstall.exe`, so the checks work
before and after the rename to CosmoSlice (decision 0148).

A check whose sources are not merged yet (T5, T6, T8) is skipped and says so.

## Modes

The signature rules follow the signing predicate of the build (decisions
0098, 0144, 0156). Windows and macOS have one mode each: Windows reads the six
Azure secrets, macOS the seven Apple secrets of `wiki/cosmyx/macos-signing.md`.

| Mode | When | Signatures |
|------|------|------------|
| `enforce` | DEV or `release/*` (or `COSMYX_SIGN_ALL_REFS`), not a pull request, not MIXED, and that OS's signing secrets all set | Every rule is a failure when broken. |
| `not-configured` | Same refs, but the secrets are not all set | Reported with a notice; a failure in strict mode. |
| `report` | Pull requests, MIXED, other refs | Reported with the count of unsigned files. |

Everything else is enforced in every mode. Strict mode (`strict` input of the
dispatch) also fails every skipped check, except skips by design (a binary
that cannot run on the runner, a fork build, no required set for that run).
Use it for release candidates.

## Allowlist

`scripts/cosmyx/artifact_checks/data/allowlist.json` lists the binaries that are
not ours (decision 0145). It ships empty, so the first signed DEV run fails on
every vendor file. To fill it:

1. Open the report of the first signed DEV run (`report.md`, or the step
   summary) and list the files signed by someone else.
2. For each publisher, add a `vendor` entry: `glob` (path inside the app, `*`
   crosses folders, case-insensitive), `publisher_subject` exactly as the
   report prints it, a `reason`, and an `expires` date if the file is meant to
   go away.
3. Use `unsigned-ok` only for an unsigned file the build cannot sign, and
   `arch-exempt` for a macOS file that legitimately has fewer architectures.
4. Open a pull request; a reviewer approves each entry. Stale entries (no
   longer matching any file) fail in enforce mode, so the list stays short.

## Settings

Repository settings the checks read (Settings, Secrets and variables, Actions):

| Setting | Kind | Effect |
|---------|------|--------|
| `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`, `AZURE_TRUSTED_SIGNING_ENDPOINT`, `AZURE_CODE_SIGNING_NAME`, `AZURE_CERT_PROFILE_NAME` | secrets (T9) | All set: signed refs are checked in `enforce` mode. Only their presence is read. |
| `BUILD_CERTIFICATE_BASE64`, `P12_PASSWORD`, `KEYCHAIN_PASSWORD`, `MACOS_CERTIFICATE_ID`, `APPLE_DEV_ACCOUNT`, `APP_PWD`, `TEAM_ID` | secrets (T15) | All set: signed refs get the macOS `enforce` mode. Only their presence is read, except `TEAM_ID`, which the macOS leg compares with the signatures (`COSMYX_MAC_TEAM_ID`, masked). |
| `COSMYX_SIGN_ALL_REFS` | variable (T9) | `true`: every non-PR, non-MIXED ref counts as signed. |
| `COSMYX_SIGN_EKU` | variable, optional | Pins our identity to the certificate profile's own EKU (`1.3.6.1.4.1.311.97.<n>...`), stable across renewals. Recommended. |
| `COSMYX_SIGN_SUBJECT` | variable, optional | Pins the exact certificate subject. |

Without pins the check passes with a warning that prints the subjects and EKUs
it saw: copy the EKU into `COSMYX_SIGN_EKU`. Once the status has been posted
once, it can be made a required check in the DEV and `release/*` branch
protection rules.

## Updating the Mesa pin

The pin is `mesa_win` in `data/expectations.json`: `version`, `url` of the
`mesa3d-<version>-release-msvc.7z` asset, its `sha256` and `size`, and the
SHA-256 of each file taken from the archive. To move it, pick a release at
least two weeks old whose release notes report no OpenGL regression for the
MSVC x64 build (26.2.6 shipped without `opengl32.dll`), take the asset's
SHA-256 from the release page (or hash the downloaded file), list the archive
to check that `x64/opengl32.dll` is there, hash the three files, update the
pin and record the change in a decision that supersedes 0161.

## Running it

- `just artifact-checks <run id>` starts the checks on a finished run
  (`just artifact-checks <run id> true` for strict mode).
- `just artifact-checks-status` lists the latest check runs.
- `just artifact-checks-local <run id>` downloads the run's artifacts for the
  host OS into `build/cosmyx/artifacts/<run id>/` (read-only `gh` calls), takes
  the built commit's data files from the local git history, and runs that OS's
  checks, the names check and the report there (`out/report.md`). Other OSes
  are skipped with a message. The Windows installer is never run locally. A
  local run cannot read the secrets: set `COSMYX_HAS_<SECRET>=true` for each of
  the six Azure secrets (Windows) or the seven Apple secrets (macOS, with
  `COSMYX_MAC_TEAM_ID` set to the team) to check in `enforce` mode.
- `just test-scripts` runs the tests (`scripts/cosmyx/tests/test_artifact_checks_*.py`
  and `artifact_checks_windows.Tests.ps1`).

## Deferred

aarch64 runs on arm runners, Windows arm64 runs, the identity of nested
Windows signatures, and the branding guard. macOS Developer ID and
notarisation are checked since T15 (decision 0156).
