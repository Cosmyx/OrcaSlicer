# feat/cosmyx-update-check (PR #122)

Analysed commits: `origin/feat/cosmyx-version..origin/feat/cosmyx-update-check` (5 commits: `bcd1e64aff`, `6787111e81`, `b83905ef31`, `3e9f327e63`, `0eca0c5dfc`). Compared with `origin/DEV` and `upstream/v2.5.2`.

## Purpose

A Cosmyx build must never be offered an OrcaSlicer release, must compare its own display version (`<base>-<patch>`, decision 0060) and must stay offline in Stealth mode. The update check (startup, Help > Check for Updates, macOS app menu) therefore reads the GitHub releases of Cosmyx/OrcaSlicer and only offers a published release tagged `v<OrcaSlicer base>.<Cosmyx patch>` (for example `v2.5.2.8`, shown `2.5.2-8`), never a draft, pre-release, dev or nightly build. "Publish to draft release" publishes the CosmoSlice artifacts of a Build all run under that convention (decision 0221).

## Parent and dependencies

- Parent: `feat/cosmyx-version` (PR #93), stacked: uses `patch_version` and `compose_display_version()`.
- Stealth mode is read through the upstream `AppConfig::get_stealth_mode()` (forced by `feat/cosmyx-stealth-mode`, rewritten by `feat/cosmyx-cloud-server`); no code dependency.
- `scripts/cosmyx/release_publish.py` expects `CosmoSlice_*` artifact names (product-name, decision 0210).
- Translations: `localization/cosmyx/update-check/` (1 msgid, French translated).
- `RELEASE_PUBLISHER` repository variable (upstream's) must be set on the fork, or the publish workflow stops at its first step.
- Upstream APIs: `GUI_App::check_new_version_sf(bool, int)`, `version_info`, `EVT_SLIC3R_VERSION_ONLINE`, `UpdateVersionDialog`, `skip_version`, `Http`.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `src/slic3r/GUI/Cosmyx/logic/UpdateCheck.hpp`, `.cpp` | Cosmyx-owned | `update_check_url`, parsing of the releases array, tag convention (four decimals, no leading zeros), newest-newer selection, numeric `skip_version` comparison. Unit tested. |
| `src/slic3r/GUI/Cosmyx/UpdateCheckRequest.hpp`, `.cpp` | Cosmyx-owned | `check_for_update(AppConfig&, by_user, version_info)`: stealth guard (menu message), HTTP request, raises `EVT_SLIC3R_VERSION_ONLINE` on the main thread. |
| `src/slic3r/GUI/GUI_App.cpp` | upstream hook | `#include "Cosmyx/UpdateCheckRequest.hpp" // Cosmyx` after `#include "slic3r/GUI/TaskManager.hpp"`. First line of `check_new_version_sf()`: `Cosmyx::check_for_update(*app_config, by_user, version_info); return; // Cosmyx: Cosmyx releases only (decision 0221)`; the upstream body stays below, unreached. |
| `src/slic3r/GUI/ReleaseNote.cpp` | upstream hook | `m_cb_stable_only->Hide(); // Cosmyx: only releases are ever offered (decision 0221)` right after `m_cb_stable_only->SetFont(Label::Body_12);` in `UpdateVersionDialog`. |
| `.github/workflows/publish_release.yml` | upstream hook | `if: ${{ false }} # Cosmyx: ...` on "Download release artifacts from build run" and "Assemble release assets"; three `# Cosmyx` steps: "Cosmyx checkout" (sparse `scripts/cosmyx`) and "Cosmyx check the tag and create the draft release" (`release_publish.py prepare`) before "Verify target is a draft release", "Cosmyx download and assemble the CosmoSlice assets" before "Upload assets to draft release". 13 lines. |
| `scripts/cosmyx/release_publish.py` | Cosmyx-owned | `prepare`, `download`, `assemble` (installers, portable zips, universal DMG, AppImages, Flatpaks, PDB archive, never the MSIX). |
| `tests/cosmyx/test_cosmyx_update_check.cpp`, `scripts/cosmyx/tests/test_update_check.py`, `test_release_publish.py` | test | Logic cases; hook pins; publish script. |
| `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md` | foundation data | T26 added to the GUI slot list. |
| `localization/cosmyx/update-check/`, `wiki/decisions/0221-update-check-cosmyx-releases.md` | data | Catalogue, decision. |
| `CHANGELOG.md` | data (docs) | One GUI line under `<!-- cosmyx-slot: T26 -->`, opened right after T11f. |

## Rebase risk zones

| Upstream file / function | In v2.5.2 | DEV vs v2.5.2 | Churn 2026 |
|--------------------------|-----------|---------------|-----------|
| `src/slic3r/GUI/GUI_App.cpp`, include block and `check_new_version_sf()` | `TaskManager.hpp` at line 24, `check_new_version_sf(bool show_tips, int by_user)` at 6605 | 32 insertions, 21 deletions in the file | 246 |
| `src/slic3r/GUI/ReleaseNote.cpp`, `UpdateVersionDialog` | Different shape: `m_cb_stable_only = new CheckBox(this);` plus a separate `stable_only_label` (`Label`) | DEV uses one `LabeledCheckBox` (8 insertions, 12 deletions) | 29 |
| `.github/workflows/publish_release.yml` | The four step names present (lines 51, 74, 86, 127) | 76 insertions, 8 deletions | 6 |

## Intent to preserve

- Only published, non-pre-release Cosmyx releases in the tag convention are ever offered, compared numerically with the running display version; nothing goes online in Stealth mode, and the menu command says why.
- The popup has no "stable updates only" control.
- The publish workflow can never publish a dev build or OrcaSlicer artifacts.

If upstream rewrote the hooked code: keep the early `return` as the first statement of whatever function all update entry points call. If `UpdateVersionDialog` is rebuilt, hide every widget of the stable-only control (on v2.5.2 that is also `stable_only_label`: one more `Hide()` line). If `publish_release.yml` renames its steps, keep the `if: false` on the artifact download and assembly and the Cosmyx steps at the same places.

## Verification

Catch2 `tests/cosmyx/test_cosmyx_update_check.cpp` (`ctest --test-dir build -C Release -R cosmyx --output-on-failure`); `just test-scripts` (hook pins, `release_publish.py`, slot list); `just decisions`. Manual: Help > Check for Updates with Stealth mode on (message), off with no fork release (newest version), with a published `v<base>.<patch+1>` (popup without the stable-only box).

## Known pitfalls

- On v2.5.2 `ReleaseNote.cpp` has the checkbox and its label as two widgets: hiding only `m_cb_stable_only` leaves the label visible.
- The branch carries feat/cosmyx-version's commits (stacked); rebase it onto the rebased version branch.
- `RELEASE_PUBLISHER` is not set on the fork yet.

## Shared files with other branches

- `src/slic3r/GUI/GUI_App.cpp`: include after `TaskManager.hpp` (outside the lines 2-4 block of version, dark-default, goldens); integration total 14 `Cosmyx` lines.
- `CHANGELOG.md` (slot T26, right after T11f, like external-machines' T24), `test_foundation.py` and decision 0003 (union of slots), `wiki/decisions` number 0221.
