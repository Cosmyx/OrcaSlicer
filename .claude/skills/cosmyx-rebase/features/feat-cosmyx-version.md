# feat/cosmyx-version (PR #93)

Measured against `origin/DEV` and the tag `upstream/v2.5.1` (DEV carries `SoftFever_VERSION` 2.6.0-dev; the tag carries 2.5.1). Branch commits analysed: `origin/DEV..origin/feat/cosmyx-version`.

## Purpose

Users and support must tell one Cosmyx build from another, and from the OrcaSlicer release it is built on. Every upstream place that shows the version to the user now shows `<SoftFever_VERSION>-<Cosmyx patch>`, for example `2.6.0-8`, or `2.6.0-dev-8` on a development base, or `2.5.1-8` on the v2.5.1 tag. The CI build files and artifacts are named after the same string plus the short commit hash (the build tag, for example `2.6.0-dev-8_aa9dac8`), so two Cosmyx builds of one upstream base no longer share a name.

Design rules (decisions 0060 to 0064):

- The upstream string is never edited. `SoftFever_VERSION` (from `version.inc`) is still parsed as an OrcaSlicer semver by 3MF, presets, the updater and the bug report link, so it stays untouched everywhere it is parsed. Only display sites go through the new helper.
- The Cosmyx patch is an integer that starts at 8 and is raised by hand for each handed-out build. It is the constant `patch_version` in `src/slic3r/GUI/Cosmyx/logic/CosmyxVersion.hpp`, the single source read by both the C++ code and `scripts/cosmyx/cosmyx_version.py`. It must be an ASCII decimal literal without a leading zero (decision 0064), at least 8.
- The upstream pre-release suffix is kept verbatim (decision 0061): the rule is a pure append, no parsing. `2.6.0-dev` + 8 gives `2.6.0-dev-8`; a release base `2.5.1` + 8 gives `2.5.1-8`.
- Foundation: the branch also carries the shared foundation (task T0, PR #86): the Cosmyx modules, the foundation hooks, the `cosmyx_tests` suite, `CHANGELOG.md`, the decision register, `justfile` and `cosmyx-checks.yml`. Those commits (`6cbd27d0fc` to `39c40f609f`) are not in DEV yet, so every Cosmyx branch lists them as its own. After PR #86 merges they vanish from each branch diff.

What the version feature does with the upstream version string on a release tag: nothing special. `version.inc` on `v2.5.1` says `set(SoftFever_VERSION "2.5.1")`; the helper appends `-8`, giving `2.5.1-8`; the script accepts it (`<x>.<y>.<z>[-<tag>]`, ASCII digits). The workflow step overrides `ver` (which upstream sets to `V<SoftFever_VERSION>` on non-PR builds and `PR-<n>` or `PR<n>` on pull requests) with the build tag on every event, including pull requests. CMake still names the NSIS installer `OrcaSlicer_Windows_Installer_V<SoftFever_VERSION>`; that name is intentionally not changed.

## Parent and dependencies

- Parent: `DEV`. Children: `feat/cosmyx-dark-default` and `test/cosmyx-gui-goldens` (both branch from this one; the goldens driver includes `logic/CosmyxVersion.hpp` and calls `display_version()` for its hello event).
- Depends on the foundation (T0, PR #86), carried inside this branch: the `src/slic3r/GUI/Cosmyx/Cosmyx.cmake` glob that picks up `logic/*.cpp`, the `tests/cosmyx` glob, `justfile`, `cosmyx-checks.yml`.
- Upstream APIs and keys it calls: `SoftFever_VERSION` macro from the generated `libslic3r_version.h` (from `version.inc` via `libslic3r_version.h.in`); `GUI_App::format_display_version()` and its `version_display` cache; `version.inc` line `set(SoftFever_VERSION "...")`; `src/slic3r/GitCommitHash.cmake` rule for the commit hash (the `git_commit_hash` environment variable, otherwise `git log -1 --format=%h`); the `env.ver`, `env.git_commit_hash` values and the two "Get the version and date on ..." steps of `build_orca.yml`.

## Changes

Foundation hooks carried here (shared with every branch, one line each, tag `// Cosmyx` or `# Cosmyx`):

| File | Kind | Change and anchor |
|------|------|-------------------|
| `src/libslic3r/CMakeLists.txt` | upstream hook | `include(Cosmyx/Cosmyx.cmake) # Cosmyx`, placed directly after `source_group(TREE ${CMAKE_CURRENT_SOURCE_DIR} FILES ${lisbslic3r_sources})` and before `if (SLIC3R_STATIC)`. |
| `src/slic3r/CMakeLists.txt` | upstream hook | `include(GUI/Cosmyx/Cosmyx.cmake) # Cosmyx`, directly after `source_group(TREE ${CMAKE_CURRENT_SOURCE_DIR} FILES ${SLIC3R_GUI_SOURCES})` and before `encoding_check(libslic3r_gui)`. |
| `tests/CMakeLists.txt` | upstream hook | `add_subdirectory(cosmyx) # Cosmyx`, between `add_subdirectory(slic3rutils)` and `add_subdirectory(fff_print)`. |
| `src/libslic3r/PrintConfig.cpp` | upstream hook | Line 2: `#include "Cosmyx/ConfigDefExtensions.hpp" // Cosmyx` (after `#include "PrintConfig.hpp"`). In `PrintConfigDef::PrintConfigDef()`: `Cosmyx::extend_print_config_def(*this); // Cosmyx` between `this->init_extruder_option_keys();` and `assign_printer_technology_to_unknown(this->options, ptFFF);`. |
| `src/libslic3r/GCode.cpp` | upstream hook | Line 2: `#include "Cosmyx/GCodeHooks.hpp" // Cosmyx` (after `#include "ArcFitter.hpp"`). |

Version feature:

| File | Kind | Change |
|------|------|--------|
| `src/slic3r/GUI/Cosmyx/logic/CosmyxVersion.hpp`, `.cpp` | Cosmyx-owned | `patch_version` (8), `compose_display_version(upstream, patch)` (returns `upstream + "-" + patch`), `display_version()` (`compose(SoftFever_VERSION, patch_version)`). wxWidgets-free, so `cosmyx_tests` compiles it. |
| `src/slic3r/GUI/GUI_App.cpp` | upstream hook | Line 2: `#include "Cosmyx/logic/CosmyxVersion.hpp" // Cosmyx` (after `#include "CloudProvider.hpp"`). In `GUI_App::format_display_version()`, the line `version_display = SoftFever_VERSION;` becomes `version_display = Cosmyx::display_version(); // Cosmyx` (neighbours: `if (!version_display.empty()) return version_display;` above and `return version_display;` below). Covers the splash screen and the About dialog copy button. |
| `src/slic3r/GUI/AboutDialog.cpp` | upstream hook | In `AboutDialog::AboutDialog()`: `auto          version_string = std::string(SoftFever_VERSION); // _L("Orca Slicer ") ...` becomes `auto          version_string = GUI_App::format_display_version(); // Cosmyx`. Anchor: the lines `vesizer->Add(0, 0, 1, wxEXPAND, FromDIP(5));` above and `wxStaticText* version = new wxStaticText(this, wxID_ANY, version_string.c_str(), ...)` below. |
| `src/slic3r/GUI/NetworkTestDialog.cpp` | upstream hook | `NetworkTestDialog::get_studio_version()`: `return wxString(SoftFever_VERSION);` becomes `return wxString(GUI_App::format_display_version()); // Cosmyx`. |
| `src/slic3r/GUI/TroubleshootDialog.cpp` | upstream hook | In `TroubleshootDialog::TroubleshootDialog()`: `auto version = new Label(this, wxString(SoftFever_VERSION), wxALIGN_CENTRE_HORIZONTAL);` becomes `auto version = new Label(this, wxString(GUI_App::format_display_version()), wxALIGN_CENTRE_HORIZONTAL); // Cosmyx`. Anchor: after the `logo_line->SetBackgroundColour(...)` line, before `wxFont version_font = GetFont();`. |
| `.github/workflows/build_orca.yml` | upstream hook (CI) | One new step inserted right after the second upstream step "Get the version and date on Windows" (the one ending `shell: pwsh`) and before the `#   Mac` comment: `- name: Name the build after the Cosmyx version` with `shell: python` and a script that runs `scripts/cosmyx/cosmyx_version.py github-env`. A `# Cosmyx:` comment line precedes the step. The script appends `ver=<build tag>` to `GITHUB_ENV`; the later value wins. |
| `scripts/cosmyx/cosmyx_version.py` | Cosmyx-owned (script) | Subcommands `version`, `build-tag [--commit]`, `github-env [--commit]`. Reads `version.inc` and the header with strict regexes (decision 0064), `MIN_PATCH = 8`, commit rule shared with `GitCommitHash.cmake`, writes `GITHUB_ENV` with `newline="\n"`. |
| `tests/cosmyx/test_cosmyx_version.cpp` | test | Catch2, see Verification. |
| `scripts/cosmyx/tests/test_cosmyx_version.py`, `test_breaker_cosmyx_version_octal.py`, `test_breaker_cosmyx_version_unicode.py` | test | unittest, see Verification. |
| `wiki/decisions/0060` to `0064` | data (docs) | Display version format, kept pre-release suffix, CI build tag, hooks and patch source, number syntax. |
| `CHANGELOG.md` | data (docs) | New file (foundation) with slots; this branch adds the GUI line under `<!-- cosmyx-slot: T6 -->`. |

Foundation-owned Cosmyx files carried unchanged: `src/libslic3r/Cosmyx/{Cosmyx.cmake, GCodeHooks.hpp, ConfigDefExtensions.{hpp,cpp}, BedTemperatureOff.*, ChtNozzle.cpp, IroningTemperature.*}`, `src/slic3r/GUI/Cosmyx/{Cosmyx.cmake, Cosmyx.hpp, logic/.gitkeep}`, `tests/cosmyx/{CMakeLists.txt, cosmyx_tests.cpp, test_cosmyx_foundation.cpp}`, `justfile`, `.github/workflows/cosmyx-checks.yml`, `scripts/cosmyx/{decisions.py, run_script_tests.py, tests/test_foundation.py}`, `wiki/decisions/0001` to `0004` and `README.md`.

## Rebase risk zones

Churn is `git log --oneline --since=2026-01-01 origin/DEV -- <file> | wc -l`; "diff" is `git diff origin/DEV upstream/v2.5.1 -- <file>`.

| Upstream file | Hook anchor present in v2.5.1? | DEV vs v2.5.1 | Churn 2026 |
|---------------|-------------------------------|---------------|-----------|
| `src/slic3r/GUI/GUI_App.cpp` | Yes: `GUI_App::format_display_version()` is identical (`version_display = SoftFever_VERSION;`), line 1 is `#include "CloudProvider.hpp"` on both. | 22 insertions, 38 deletions elsewhere in the file (unrelated code). | 246 (very high; only a risk for line-based patch context, the touched lines are stable) |
| `src/slic3r/GUI/AboutDialog.cpp` | Yes, original line at 266 on the tag; `GUI_App::format_display_version()` is already used by the copy button there. | No difference. | 11 |
| `src/slic3r/GUI/NetworkTestDialog.cpp` | Yes (`return wxString(SoftFever_VERSION);`). | 1 deletion elsewhere. | 7 |
| `src/slic3r/GUI/TroubleshootDialog.cpp` | Yes (`SoftFever_VERSION` at line 188; the tag also still uses it at the bug-report URL and the copy info text, which stay on purpose). | 8 insertions, 9 deletions elsewhere. | 19 |
| `src/libslic3r/CMakeLists.txt` | Yes (`source_group(TREE ...)` at line 615). | 7 insertions, 24 deletions elsewhere. | 127 |
| `src/slic3r/CMakeLists.txt` | Yes (`source_group(TREE ...)` at line 946). | 1 insertion, 11 deletions. | 205 |
| `tests/CMakeLists.txt` | Yes (`slic3rutils` and `fff_print` lines present). | 3 insertions, 5 deletions. | 9 |
| `src/libslic3r/PrintConfig.cpp` | Yes (`this->init_extruder_option_keys();` at line 1003, `ptFFF` line below). | 30 insertions, 307 deletions elsewhere (large drift). | 385 (highest) |
| `src/libslic3r/GCode.cpp` | Yes (line 1 `#include "ArcFitter.hpp"`). | 147 insertions, 269 deletions elsewhere. | 342 |
| `.github/workflows/build_orca.yml` | Yes: both "Get the version and date on Ubuntu and macOS" and "... on Windows" steps exist on the tag; the Windows one ends with `shell: pwsh` followed by `#   Mac`. On the tag the non-PR value is `ver=V<ver_pure>`, PR is `PR-<n>` (Unix) / `PR<n>` (Windows). | 55 insertions, 130 deletions (DEV is far ahead: macOS, signing and cache steps). | 86 |

Other checks:

- `version.inc`: tag `2.5.1`, DEV `2.6.0-dev`; one line differs, and the Cosmyx code reads it at build time. No hook lives in `version.inc`; never edit it for Cosmyx.
- `libslic3r_version.h` / `SoftFever_VERSION`: still generated on the tag.
- `GitCommitHash.cmake`: unchanged between DEV and the tag (no diff); the script's commit rule still matches it.
- The `shell: python` step relies on the GitHub runners' Python; present on all runner images used by `build_orca.yml`.

## Intent to preserve

- Every user-facing version label shows `<SoftFever_VERSION>-<patch>` and nothing else is renamed. `SoftFever_VERSION` stays pristine wherever it is parsed (3MF, presets, updater, logs, stored `version` app config key, G-code viewer header, upstream bug report URL).
- The patch lives in exactly one place, the header line `inline constexpr int patch_version = N;`, which the script reads; the C++ and Python composition rules must agree (append, keep suffix).
- CI artifacts and files use `ver=<display version>_<short hash>` for every event including pull requests, via one step after the upstream version steps; the NSIS installer's CMake name and `ver_pure` stay unchanged.

If upstream rewrites the hooked code: if `format_display_version()` disappears or stops being the central accessor, re-hook where the dialogs build their label (re-introduce a single call to `Cosmyx::display_version()` at each display site; grep `SoftFever_VERSION` under `src/slic3r/GUI` and keep the non-display ones). If upstream restructures the version steps of `build_orca.yml` (for example a single version step, or a reusable workflow), keep the Cosmyx step after whichever step finally writes `ver` to `GITHUB_ENV`; if `ver` is renamed, make the script write the new variable name. If upstream changes how the version is obtained (for example derives it from git tags instead of `version.inc`), change `upstream_version()` in the script and the `SoftFever_VERSION` macro use in `CosmyxVersion.cpp` together, never one without the other.

## Verification

Catch2 (`tests/cosmyx`, target `cosmyx_tests`, tag `[cosmyx]`, `[CosmyxVersion]`): "Cosmyx patch numbers start at 8", "The display version appends the Cosmyx patch to the upstream version", "The display version keeps an upstream pre-release suffix", "The built display version is SoftFever_VERSION followed by the patch" (regex `\d+\.\d+\.\d+(-[0-9A-Za-z.]+)?-\d+`). Foundation tests in `test_cosmyx_foundation.cpp`: "PrintConfigDef runs the Cosmyx dispatcher", "Every Cosmyx extender can run on a definition", "add_option registers a Cosmyx option", "Upstream options keep their upstream ordinals", "Every Cosmyx option default is within its own range". Run: `ctest --test-dir build -C Release -R cosmyx --output-on-failure` (or `cosmyx_tests "[cosmyx]"`).

Script tests (`just test-scripts`, runs `scripts/cosmyx/run_script_tests.py`): `test_cosmyx_version.py` (classes `ComposeTests`, `ReadTests`, `RealRepositoryTests` which reads the real `version.inc` and header, `CommitTests`, `CliTests`, `WorkflowWiringTests` checking exactly one step writes the build tag and that it runs after both upstream version steps), `test_breaker_cosmyx_version_octal.py`, `test_breaker_cosmyx_version_unicode.py`, `test_foundation.py`. `just decisions` checks the register.

Manual checks after a rebase onto v2.5.1:

1. `python3 scripts/cosmyx/cosmyx_version.py version` prints `2.5.1-8` (or the current patch).
2. `python3 scripts/cosmyx/cosmyx_version.py build-tag --commit abcdef1` prints `2.5.1-8_abcdef1`.
3. `git grep -n "// Cosmyx" -- src/slic3r/GUI/AboutDialog.cpp src/slic3r/GUI/GUI_App.cpp src/slic3r/GUI/NetworkTestDialog.cpp src/slic3r/GUI/TroubleshootDialog.cpp` lists the five hook lines.
4. `git grep -n SoftFever_VERSION -- src/slic3r/GUI` still lists the parse sites (updater, 3MF, log, bug-report URL) and no display site.
5. `build_all` (started by hand: `just build-all <branch>`) produces artifacts named `..._2.5.1-8_<hash>`; the About dialog shows `2.5.1-8`.

## Known pitfalls

- `5d4258797a`: Python `int("010")` is 10 while C++ reads `010` as octal 8, and `\d` matched non-ASCII digits; the script now accepts only ASCII decimal without a leading zero (decision 0064). Never loosen it.
- `c34bce56ac`: on the Windows runner `write_text` wrote CRLF into the fake `GITHUB_ENV`; the fixture is written as bytes and the script opens `GITHUB_ENV` with `newline="\n"` (a test pins the open mode). A CRLF in `GITHUB_ENV` breaks `ver` on Windows.
- `5fbe728f6f` and `57866a96b9`: the `cosmyx-checks` workflow path filters and the justfile imports of planned recipe files (`version.just` is imported with `import?` but is not created by this branch).
- `ver` on release-tag builds: do not assume `ver_pure` equals `ver`; the step replaces `ver` only, `ver_pure` keeps the plain upstream number.
- `shell: python` needs the runner Python on `PATH`; if a runner image stops shipping it, add `actions/setup-python` before the step.

## Shared files with other branches

- `GUI_App.cpp`: line 2 here is the version include; `feat/cosmyx-dark-default` adds line 3 (`Cosmyx/ColorMode.hpp`), `test/cosmyx-gui-goldens` adds line 4 (`Cosmyx/GoldenDriver.hpp`) and its own call after `this->post_init();`; `feat/cosmyx-install-paths` places its include after `#include "Downloader.hpp"` precisely to avoid this stack (decision 0181). Rebase these includes in order.
- `.github/workflows/build_orca.yml`: this branch adds one step after the Windows version step; `feat/cosmyx-windows-signing` adds three steps further down (setup before "Build slicer Win", sign before "Pack unit tests Win", verify after "Verify Windows signatures"). The signing wiring test picks its steps by name, so both can coexist.
- `CHANGELOG.md`: slots T0 to T13 and T16 (this branch fills T6). `wiki/decisions/`: this branch uses 0060 to 0064; the other branches use 0090-0099 (signing), 0136-0139 (dark), 0162-0179 (goldens), 0180-0185 (install paths). `wiki/decisions/0003-changelog-slots.md` and `scripts/cosmyx/tests/test_foundation.py` list every slot, the goldens branch edits both to add T16.
- Foundation files (`justfile`, `cosmyx-checks.yml`, `scripts/cosmyx/{decisions.py, run_script_tests.py}`, `tests/cosmyx/*`, the foundation hooks) are identical in every branch; the first merge (PR #86) wins and the others rebase to nothing.
- `tests/cosmyx/CMakeLists.txt` globs `logic/*.cpp`; `CosmyxVersion.cpp` is shared with the goldens driver.
