# feat/cosmyx-translations (PR #95)

## Purpose

Cosmyx adds its own UI strings (the CHT nozzle option, the ironing temperature option, the Cosmyx calibration model menu entries). OrcaSlicer loads one gettext catalogue per language, compiled from `localization/i18n/<lang>/OrcaSlicer_<lang>.po`, and upstream regenerates those files constantly. Committing Cosmyx strings into them would conflict on nearly every upstream merge, and the zero-conflict rule forbids that.

This branch keeps the Cosmyx strings in Cosmyx-owned catalogues and merges ("grafts") them into the upstream `.po` files in place, in CI, right before the build compiles the `.mo` files. Every desktop build leg (Windows, macOS, Linux, Flatpak) does it. The edited tracked files are then hidden from `git diff` with the skip-worktree bit so the build is not stamped `-dirty`. The user-visible effect is that the Cosmyx labels appear translated in all 22 OrcaSlicer languages instead of in English.

Decisions: 0080 (graft at build time), 0081 (one catalogue per feature), 0082 (superseded), 0083 (standard-library PO tooling), 0084 (upstream strings left out of templates), 0085 (xgettext extraction and seeding), 0086 (Flatpak is grafted), 0087 (skip-worktree helper), 0088 (UTF-8 catalogues only). Changelog slot: T8, area `i18n`.

Important scoping note: the range `origin/DEV..origin/feat/cosmyx-translations` also contains the six foundation commits of PR #86 (branch `chore/cosmyx-foundation`, slot T0): the Cosmyx libslic3r and GUI modules with their upstream hooks, the `cosmyx_tests` Catch2 suite, the justfile, `cosmyx-checks.yml`, CHANGELOG.md and the decision register 0001-0005. They are listed below as "foundation (PR #86)". The translation work proper is the commits from `7a446c060b` to `f86446b4fb`. Once #86 merges into DEV the foundation rows disappear from this PR.

## Parent and dependencies

- Parent: `DEV` (PR base is DEV). It depends on PR #86 (`chore/cosmyx-foundation`), whose commits it carries until that merges.
- Children stacked on it: `feat/cosmyx-translations-fill` (#108) and `ci/cosmyx-branding-engine` (#99), which in turn parents logos and colours.
- Upstream things it depends on:
  - `localization/i18n/<lang>/OrcaSlicer_<lang>.po` for the 22 shipped languages (ca cs de en es eu fr hu it ja ko lt nl pl pt_BR ru sv th tr uk vi zh_CN zh_TW) and `localization/i18n/OrcaSlicer.pot`. The language list is read from the folders of `localization/i18n`; each Cosmyx catalogue copies `Language` and `Plural-Forms` from the matching Orca header.
  - `.github/workflows/build_orca.yml`: the step named `Checkout` (`actions/checkout@v7`, `lfs: 'false'`), the next step `load cached deps`, and the input `macos-combine-only`.
  - The Flatpak job: today `.github/workflows/build_flatpak.yml` (DEV only), step `- uses: actions/checkout@v7`. The Flatpak manifest `scripts/flatpak/com.orcaslicer.OrcaSlicer.yml` copies `localization/`, `resources/` and `src/` from the working tree with `type: dir` sources, which is why edits made after checkout reach the sandbox.
  - `src/slic3r/GitCommitHash.cmake`: appends `-dirty` when `git diff --quiet HEAD` fails and no `git_commit_hash` env is set. This is the reason for the skip-worktree helper.
  - xgettext keywords of the upstream `gettext_make_pot` target: `L`, `_L`, `_u8L`, `L_CONTEXT:1,2c`, `_L_CONTEXT:1,2c`, `_u8L_CONTEXT:1,2c`, `_L_PLURAL:1,2`, `TRN` comments, `--boost`. `i18n_extract.py` repeats this list; keep it in sync if upstream changes the target.
  - Foundation hooks into `PrintConfig.cpp`, `GCode.cpp` and three CMake files (see Changes).

## Changes

Foundation rows (PR #86, inherited):

| File | Kind | What it does |
|---|---|---|
| `src/libslic3r/CMakeLists.txt` | upstream hook | One line after `source_group(TREE ${CMAKE_CURRENT_SOURCE_DIR} FILES ${lisbslic3r_sources})`: `include(Cosmyx/Cosmyx.cmake) # Cosmyx`. |
| `src/slic3r/CMakeLists.txt` | upstream hook | One line after `source_group(TREE ${CMAKE_CURRENT_SOURCE_DIR} FILES ${SLIC3R_GUI_SOURCES})`, before `encoding_check(libslic3r_gui)`: `include(GUI/Cosmyx/Cosmyx.cmake) # Cosmyx`. |
| `tests/CMakeLists.txt` | upstream hook | Between `add_subdirectory(slic3rutils)` and `add_subdirectory(fff_print)`: `add_subdirectory(cosmyx) # Cosmyx`. |
| `src/libslic3r/PrintConfig.cpp` | upstream hook | Line 2: `#include "Cosmyx/ConfigDefExtensions.hpp" // Cosmyx`. In `PrintConfigDef::PrintConfigDef()` between `this->init_extruder_option_keys();` and `assign_printer_technology_to_unknown(this->options, ptFFF);`: `Cosmyx::extend_print_config_def(*this); // Cosmyx`. |
| `src/libslic3r/GCode.cpp` | upstream hook | Line 2, after `#include "ArcFitter.hpp"`: `#include "Cosmyx/GCodeHooks.hpp" // Cosmyx`. |
| `src/libslic3r/Cosmyx/*`, `src/slic3r/GUI/Cosmyx/*`, `tests/cosmyx/*` | Cosmyx-owned / test | Module folders (globbed by `Cosmyx.cmake`, `CONFIGURE_DEPENDS`) and the `cosmyx_tests` suite. |
| `justfile`, `scripts/cosmyx/just/*.just`, `scripts/cosmyx/run_script_tests.py`, `scripts/cosmyx/decisions.py` | Cosmyx-owned | Recipe entry point (feature recipe files loaded with `import?`), script test runner, decision register checker. |
| `.github/workflows/cosmyx-checks.yml` | CI | Runs `just test-scripts` and `just decisions` on Linux, macOS and Windows for PRs to DEV. |
| `CHANGELOG.md`, `wiki/decisions/0001-0005*.md`, `wiki/decisions/README.md` | Cosmyx-owned | Changelog with per-task slot markers (`<!-- cosmyx-slot: Tn -->`) and the decision register. |

Translation rows (this PR proper):

| File | Kind | What it does |
|---|---|---|
| `.github/workflows/build_orca.yml` | upstream hook | Three lines inserted between the `Checkout` step and `- name: load cached deps`:<br>`      - name: Prepare Cosmyx sources # Cosmyx`<br>`        if: ${{ !(runner.os == 'macOS' && inputs.macos-combine-only) }} # Cosmyx`<br>`        uses: ./.github/actions/cosmyx-prepare # Cosmyx`<br>Skipped on the macOS combine-only leg, which compiles nothing. |
| `.github/workflows/build_flatpak.yml` | upstream hook | Two lines directly after the line `    - uses: actions/checkout@v7`:<br>`    - name: Prepare Cosmyx sources # Cosmyx`<br>`      uses: ./.github/actions/cosmyx-prepare # Cosmyx` |
| `.github/actions/cosmyx-prepare/action.yml` | CI (Cosmyx-owned composite action) | In order: trust the workspace for git inside a job container (`safe.directory`, avoids "dubious ownership" exit 128); pick the container's `python3` (>= 3.9) if in a container, else `actions/setup-python@v7` 3.12 with `update-environment: false`; export `COSMYX_PYTHON`; run the graft, worktree helper tests (`COSMYX_TEST_PROFILE=prepare`); run `scripts/cosmyx/i18n_graft.py`; last step `scripts/cosmyx/worktree_clean.py hide`. Every step that edits tracked files must stay above `hide`. The branding engine branch adds its steps here. |
| `localization/cosmyx/<feature>/messages.pot` and `<lang>.po` | data | Three features: `cht-nozzle` (msgid `CHT`), `ironing-temperature` (`Ironing temperature` and the "Nozzle temperature while this filament irons..." description), `models` (15 msgids: `Calibration Suggestion`, `Cosmyx 3D Models`, `Calibration Models Dual Head`, `Calibration Models Single Head`, `Cosmyx Handy Models`, `Calage 1 SNDT`, `Cosmyx Calage 2 SNDT`, `Cosmyx Calage 3 SNDT`, `Cube Bicolore`, `Cosmyx Calage 1 Nova`, `Cosmyx Cube`, `Control Tension Belt`, `Support Bobine`, ...). Total 18 msgids x 22 languages (+ `en.po`). Schema: standard PO keyed by (msgctxt, msgid); header copies `Language` and `Plural-Forms` from the Orca catalogue; no file carries the `OrcaSlicer` prefix (upstream tooling globs `OrcaSlicer*.po` and `scripts/run_gettext.bat` compiles every `*.po` under `localization/i18n`). In this PR the `<lang>.po` are seeded (39 translated entries carried from the old branch `cosmyx-2.3.1-7`: 38 in the 22 languages plus 1 in `en.po`; `just i18n-graft-dry-run` sums 39 "appended"), the rest empty; #108 fills them. |
| `scripts/cosmyx/i18n_graft.py` | Cosmyx-owned tool | Standard-library PO reader/writer and the graft. Rules: translated non-fuzzy Cosmyx entry replaces the Orca entry of the same key and is not fuzzy; fuzzy or empty Cosmyx entries never win; Cosmyx-only keys are appended; obsolete entries dropped; plurals kept; Orca header kept; same key in two features is an error; a language Orca lacks is a warning. UTF-8 only (decision 0088). Every check runs before any write. Untouched Orca entries are byte-identical; each catalogue keeps its dominant line ending (CRLF on Windows checkouts). `--dry-run` writes nothing. |
| `scripts/cosmyx/i18n_extract.py` | Cosmyx-owned tool | `extract` runs xgettext over `src/**/Cosmyx/**`, one template per feature, then refreshes every `<lang>.po`; `feature_for()` maps a source stem to a feature (`STEM_FEATURES` explicit entries, else kebab-case stem without `cosmyx-`, folded into the shortest known feature that is a word prefix). Strings already in `localization/i18n/OrcaSlicer.pot` are dropped from templates (decision 0084). `seed --ref REF` fills empty msgstr from the Orca catalogues of a git ref, exact (msgctxt, msgid) matches only. |
| `scripts/cosmyx/worktree_clean.py` | Cosmyx-owned tool | `hide` sets skip-worktree on every tracked file differing from HEAD then asserts `git diff --quiet HEAD`; `show` lists hidden files; `unhide [PATHSPEC...]` clears the bit and restores committed content, with `GIT_LITERAL_PATHSPECS=1` for the checkout so file names with `[ * ?` are exact. Shared with the branding engine. |
| `scripts/cosmyx/just/i18n.just` | Cosmyx-owned | Recipes `i18n-extract`, `i18n-extract-docker`, `i18n-seed REF`, `i18n-graft-dry-run`, `i18n-graft`, `i18n-ungraft`, `worktree-hidden`. |
| `scripts/cosmyx/tests/test_i18n_graft.py`, `test_i18n_extract.py`, `test_worktree_clean.py`, `test_breaker_i18n_po.py`, `test_breaker_i18n_worktree_clean.py` | test | Graft rules, real French catalogue round-trip, CRLF, UTF-8, malformed input, extraction, hide/unhide on a temporary repository, the action's step order (`safe.directory` first). |
| `CHANGELOG.md`, `wiki/decisions/0080-0088*.md` | docs | Line under slot T8; nine decisions. |

## Rebase risk zones

Checked against `upstream/v2.5.1` (merge-base with DEV is 65aab6bcf7, 2026-10-27; 185 commits only in the tag, 310 only in DEV).

1. **Flatpak hook anchor does not exist in v2.5.1 (top risk).** `.github/workflows/build_flatpak.yml` is a DEV-only file (split out of `build_all.yml` by commit a4de8cb891, #17202). In v2.5.1 the Flatpak build is the inline `flatpak:` job of `.github/workflows/build_all.yml` (about line 268, container `ghcr.io/flathub-infra/flatpak-github-actions:gnome-50`), whose steps are `Remove unneeded stuff to free disk space`, then `- uses: actions/checkout@v7`, then `Get the version and date`. The two hook lines must be re-anchored after that checkout line inside `build_all.yml`, tagged `# Cosmyx`; do not recreate `build_flatpak.yml`. The composite action itself is unaffected.
2. `build_orca.yml` hook: anchor still present in v2.5.1 (`Checkout` at line 42, `load cached deps` at line 47, `macos-combine-only` input at line 20). Upstream touched this file 4 times on the tag side and 58 times on DEV in the last six months, so re-check that no step was inserted between Checkout and the hook and that the `if:` expression still names `inputs.macos-combine-only`.
3. Msgid collisions: none of the 18 Cosmyx msgids (`CHT`, `Ironing temperature`, `Calibration Suggestion`, `Cosmyx 3D Models`, the model names) exists in `OrcaSlicer.pot` of v2.5.1 or DEV (checked with grep). The graft dry-run on a v2.5.1 tree with this branch's catalogues gives, for every language, `0 replaced, 18 appended, 0 kept OrcaSlicer, 0 dropped obsolete`. A rebase can only collide if upstream later adds one of these msgids; then the Cosmyx translation silently replaces the Orca one (rule: translated Cosmyx entry wins) and decision 0084 would have dropped it from the template on the next `just i18n-extract`.
4. Language set: `localization/i18n` has the same 22 language folders plus `en` in v2.5.1 and DEV. A new upstream language needs a `<lang>.po` in every Cosmyx feature folder (the graft test checks every feature has every language and the same msgids as its template).
5. `localization/i18n/OrcaSlicer.pot` churns heavily (88 DEV commits in six months, 10 on the tag side) but the graft only appends to, or replaces entries in, the `.po` files, so churn does not break it; it only changes extraction filtering.
6. Foundation hooks (rows above): the PrintConfig.cpp anchors (`init_extruder_option_keys();` then `assign_printer_technology_to_unknown(this->options, ptFFF);` at lines 1003-1004), line 1 of GCode.cpp (`#include "ArcFitter.hpp"`), the `source_group` lines (libslic3r CMake line 615, GUI CMake line 946 in v2.5.1) and the `slic3rutils` / `fff_print` pair in `tests/CMakeLists.txt` all still exist in v2.5.1. PrintConfig.cpp and GCode.cpp are hot files (395 and 351 DEV commits in a year): hooks at line 2 and at stable call sites are chosen to survive, but verify the include is still after the first include and not inside a conditional.
7. `src/slic3r/GitCommitHash.cmake` still has the `git diff --quiet HEAD` / `-dirty` logic in v2.5.1 (it rarely changes: 1 commit in six months). If upstream reworks how the suffix is computed, the hide step may become unnecessary or insufficient.

## Intent to preserve

- Cosmyx strings never live in `localization/i18n` in git; they are merged only at build time, only in CI, and a failure of the graft (bad catalogue, duplicate key, non-UTF-8) fails every build leg before the long compile.
- A translated Cosmyx entry beats the Orca entry; an empty or fuzzy one never does; untouched Orca entries stay byte for byte; each file keeps its own line ending.
- The build is never stamped `-dirty`: `hide` is always the last step of the prepare action, and anything that edits tracked files goes before it.
- Every desktop build, Flatpak included, runs the action once.
- Upstream edits are limited to the hook lines tagged `# Cosmyx` / `// Cosmyx`. If an anchor moved or vanished, re-anchor the single hook next to the equivalent stable line (after the checkout step, after the first include, after `source_group`), never copy the old surrounding hunk or reintroduce a deleted upstream file. If upstream reorganised workflows (the `build_all.yml` vs `build_flatpak.yml` case), hook the job that now performs the checkout.
- Language, translation content and extracted msgids are data: do not regenerate or reword translations while rebasing. Run `just i18n-extract` only if Cosmyx source strings changed.
- No status gating applies here (that is the branding tables' job).

## Verification

Run from the repository root after the rebase:

- `just test-scripts` (all script tests; Pester only where PowerShell exists) or, narrower, with `PYTHONDONTWRITEBYTECODE=1 COSMYX_TEST_PROFILE=prepare`: `python3 -m unittest discover -s scripts/cosmyx/tests -p test_i18n_graft.py -t scripts/cosmyx/tests`, the same for `test_worktree_clean.py` and `test_i18n_extract.py`.
- `just i18n-graft-dry-run` (prints per-language counts, writes nothing). Expect 0 errors and no warning about a missing language.
- `just i18n-graft` then check, then `just i18n-ungraft` to restore (it unhides first). On a machine with gettext: `msgfmt --check-format --check-header -o /dev/null localization/i18n/fr/OrcaSlicer_fr.po` after the graft. Local macOS has no msgfmt/xgettext by default; `just i18n-extract-docker` runs extraction in Docker.
- `just worktree-hidden` shows what `hide` hid on a prepared tree.
- `just decisions` (register consistency), `git grep -n Cosmyx -- .github src tests` to list every hook and confirm each is still present once.
- Hook anchors: `git show <new-base>:.github/workflows/build_orca.yml | grep -n 'Checkout\|load cached deps\|macos-combine-only'`, and find the Flatpak job's checkout line.
- C++ side (foundation): the `cosmyx_tests` target compiles and passes in CI (`build_all` via `just build-all <branch>`); no local dependency build is available.

## Known pitfalls

- `73321ba242` Windows runners check out CRLF (`core.autocrlf`); the graft used to write mixed endings. It now reads LF text, remembers the dominant ending and writes only that.
- `2689120329` In a job container (Flatpak runs in a Fedora image) git refused the workspace as dubious ownership; the action now adds `safe.directory` first, and a test pins that it stays the first step.
- `85bf240be2` Grafted catalogues made push builds `-dirty`; `worktree_clean.py hide` was added and shared with branding.
- `07e927ca49` (tests `1f20c098e1`) PO reader split on Unicode line separators (U+2028 etc.) and accepted unescaped quotes; a file without a final newline got the next entry glued on; non-UTF-8 charsets were grafted silently. Now LF-only splitting, strict quotes, newline restoration, `require_utf8()`.
- `f86446b4fb` (test `fd064cd602`) `unhide` passed file names as glob pathspecs, so `x[ab].txt` restored `xa.txt`; checkout now uses `GIT_LITERAL_PATHSPECS`.
- `04f9955f54` (pushed after the v2.5.1 pass, 2026-11-20) the graft's `main()` falls back to `$GITHUB_STEP_SUMMARY`, so the graft unit tests appended fake tables to the real CI job summary; the tests now drop the variable, and a regression test runs them as a subprocess with it set. The engine and every child were restacked onto it (same patches).
- `f6dd26c085` an obsolete `version` catalogue was dropped because the redone display version no longer adds the string; a catalogue with msgids found nowhere in sources would be appended as dead entries in every Orca catalogue.
- `abcf9e2295` / `61f7af5bf6` the action was widened so the Flatpak build is prepared as well (decision 0086 supersedes 0082).
- Zsh note for agents: write `${REF}:path` in shell when reading blobs from a ref, `$REF:path` expands modifiers.
- v2.5.1 pass (copy tip `ae7591df8d`): `abcf9e2295` hit modify/delete on `build_flatpak.yml`; the two prepare lines went after `    - uses: actions/checkout@v7` of the `flatpak:` job in `build_all.yml` (line 299, before "Get the version and date"), CRLF kept. No script test pins that Flatpak hook, so a lost hook would only show as an untranslated Flatpak build. Decisions 0082/0086 still name `build_flatpak.yml` (DEV layout).
- v2.5.2 pass (copy tip `76cb75b5b4`): the same modify/delete on `abcf9e2295`, resolved the same way; the prepare lines now sit at lines 304-305 of `build_all.yml` (four lines lower). The branch gained `04f9955f54` after the v2.5.1 pass (see above); it replayed clean.

## Shared files with other branches

- `CHANGELOG.md`: this branch owns the line under `<!-- cosmyx-slot: T8 -->` (area `i18n`). `feat/cosmyx-translations-fill` adds its own line directly above it under the same slot; resolve by keeping both, never moving a slot marker. Every other branch has its own slot (T11a engine, T11b logos, T11c colours...). Slot markers are owned by the foundation (T0) and checked by `test_foundation.py`.
- `wiki/decisions/`: 0001-0005 foundation, 0080-0088 this branch; numbers must stay unique across branches (`just decisions` enforces). The engine and later branches use 0120+.
- `.github/actions/cosmyx-prepare/action.yml`: created here; `ci/cosmyx-branding-engine` adds the branding test line and the `Apply Cosmyx branding` step between the graft and `hide`. Keep `hide` last and the graft before branding.
- `scripts/cosmyx/worktree_clean.py`: reused by the branding engine and its tests.
- `justfile`: foundation file; it already carries every `import?` line (`branding.just`, `i18n.just`, ...). This branch only adds `scripts/cosmyx/just/i18n.just`, so no justfile edit is needed.
- `.github/workflows/cosmyx-checks.yml` path filters include `localization/cosmyx/**` and `.github/actions/**`; other branches edit the same `paths:` lists (merge conflict hot spot when two branches add a path).
- `localization/cosmyx/<feature>/`: each feature branch (models, cht-nozzle, ironing-temperature) re-runs `just i18n-extract` and may touch its own folder; the three folders exist here for all of them, so extraction on a feature branch can conflict with this one in `messages.pot` / `<lang>.po`.
- `.github/workflows/build_orca.yml` and the Flatpak workflow are shared with every branch that needs a CI hook; only this one adds the prepare step, other branches reuse the action.
