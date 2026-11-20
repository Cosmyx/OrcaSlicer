# ci/cosmyx-branding-engine (PR #99)

## Purpose

The Cosmyx build must look like CosmoSlice (logos, violet colours, product name, forced dark mode) while the git tree stays OrcaSlicer, so that merging upstream into `DEV` never conflicts. Editing hundreds of upstream images, colours and strings in git would conflict on each upstream change, and CMake installs `resources/` whole, so replacement files kept inside it would ship next to the originals.

This branch adds the engine that applies the branding at build time, to the checked-out tree, from tables under `cosmyx-src/branding/`, with guards before and after, an exact revert, and a clean git tree (the edited files are hidden from `git diff`). Nothing upstream-owned is edited in git: the only upstream-facing change is a step inside the existing composite action `.github/actions/cosmyx-prepare`. The engine itself ships only the image manifest (560 rows, all `missing`) and an empty overlay; the content comes from sibling branches: logos (#101), colours (#102), and later product name, SVG candidates, dark default.

Policy: every row needs the user's validation before a release. Development builds (pull requests whatever their target, `DEV`, `MIXED`, any other branch, local) apply every recorded overlay and only warn about `missing` and `to-validate` rows; release builds (`refs/heads/release/*` and tags) fail on them (decision 0121).

Decisions: 0120 (build-time engine from tables), 0121 (status policy), 0122 (guards G1-G8 and their severity), 0123 (manifest discovered from the tree). Changelog slot T11a (area `CI-release`).

## Parent and dependencies

- Parent: `feat/cosmyx-translations` (PR #95, which itself needs #86). PR #99 targets `DEV`, so it shows the parent's commits until they merge.
- Reuses from the parent: `.github/actions/cosmyx-prepare/action.yml` (the engine step goes after the graft and before `hide`), `scripts/cosmyx/worktree_clean.py hide` (so a branded tree is not `-dirty`), the `COSMYX_PYTHON` env exported by the action, the justfile `python` variable and its `import?` lines, the CHANGELOG slot markers, `wiki/decisions`.
- Children: `feat/cosmyx-logos` (#101), `feat/cosmyx-colours` (#102), and the not-covered siblings that feed `product-name/` and the SVG candidates. Their recipes are loaded by `import?` lines at the end of `branding.just` (`branding-logos.just`, `branding-colours.just`, `branding-candidates.just`, `branding-product-name.just`).
- Upstream files it depends on (all read, none edited in git):
  - Every SVG under `resources/images` and `resources/web` holding a teal colour (HSL hue 160-190, saturation >= 0.25, lightness >= 0.15, `#00AE42` and `#1F8EEA` excluded), found by `just brand-sync`.
  - Branding image patterns in `manifest.py` `LOGO_PATTERNS`: `resources/Icon.icns`, `resources/images/OrcaSlicer*`, `resources/images/splash_logo*`, `resources/images/studio_logo*`, `resources/images/stl.icns`, `resources/images/gcode.icns`, `resources/web/image/logo*`, `scripts/msix/assets/*`.
  - The upstream hashes recorded in each row (`upstream_sha256`, SHA-256 over LF bytes for SVG, raw bytes otherwise).
  - `src/slic3r/GitCommitHash.cmake` (`-dirty` logic), indirectly via the hide step.
  - Git (for guard G7 `git grep`, skipped with a warning outside a checkout) and Python >= 3.9, standard library only.

## Changes

| File | Kind | What it does |
|---|---|---|
| `.github/actions/cosmyx-prepare/action.yml` | CI (Cosmyx-owned action, edited) | Adds a test line `python -m unittest discover -s scripts/cosmyx/tests -p 'test_branding_*.py' -t scripts/cosmyx/tests` (run with `COSMYX_TEST_PROFILE: prepare`) and the step `Apply Cosmyx branding`: `"$COSMYX_PYTHON" scripts/cosmyx/branding/cli.py apply --ci`, between `Graft the Cosmyx translations` and `Hide the build-time edits from git diff`. No upstream workflow file is edited. |
| `scripts/cosmyx/branding/__init__.py` | Cosmyx-owned | Shared paths (`BRAND_DIR = cosmyx-src/branding`, `MANIFEST_DIR`, `OVERLAY_DIR`, `COLOURS_FILE`, `PRODUCT_NAME_DIR`, `TABLES_DIR = wiki/cosmyx/branding-assets`, `STATE_DIR = build/cosmyx/branding-state`, `REPORT_FILE`), groups (`logos`, `icons-a-m`, `icons-n-z`, `web`), `COSMYX_PATHS` (files where Cosmyx colours/names may appear), `Finding`, hashing, canonical JSON, the hex colour rule, `ref_kind()` (release vs development, `COSMYX_BRAND_REF` override). |
| `scripts/cosmyx/branding/manifest.py` | Cosmyx-owned | Row schema, discovery and `sync` / `refresh` / `validate`. Row fields in frozen order: `path`, `format` (svg png ico icns gif), `size`, `usage`, `kind` (logo or recolour), `source` (cosmoslice, candidate, derived, user, or null), `source_ref`, `status` (missing, to-validate, validated), `upstream_sha256`, `override_sha256`. Tables are `{"schema": 1, "group", "rows"}`, rows sorted by path, two-space JSON with final newline. A row never changes group. |
| `scripts/cosmyx/branding/overlay.py`, `apply.py`, `textpatch.py` | Cosmyx-owned | Overlay copy (a symlinked overlay file or folder is a G2 error), the apply/revert pipeline (pre-guards, overlay, colours, product name, post-guards, report) with a backup of every file under `build/cosmyx/branding-state/` before its first write, and exact, counted, all-or-nothing text patches (`{file, old, new, count, reason}`; colour rows use `find`/`replace`). Matching is done on LF text; each patched file is written back with its own dominant line ending. A path that resolves outside the repo or differs only by case from the on-disk name is refused on every OS. |
| `scripts/cosmyx/branding/guards.py` | Cosmyx-owned | G1 overlay hash and applied hash, G2 no orphan overlay, G3 upstream file exists with the recorded hash, G4 every teal SVG and branding image has a row, G5 colour counts and teal residue (needs colours.json), G6 tables valid, canonical and review tables rendered, G7 no palette colour or "CosmoSlice" in tracked upstream-owned files (`git grep`, with `allow_residue` exceptions), G8 product-name patch counts and unchanged `SLIC3R_APP_KEY` lines. G3 and G4 are drift: warning on development builds, error on release builds; everything else is an error everywhere. A guard never raises: one that cannot run is an error finding. |
| `scripts/cosmyx/branding/cli.py`, `render.py` | Cosmyx-owned | Commands `check`, `apply [--ci]`, `revert`, `sync`, `refresh PATTERN`, `validate PATTERN --i-am-the-user`, `render [--check]`. `validate` refuses without the flag (or `COSMYX_BRAND_VALIDATOR`), without a terminal, in CI (`CI`/`GITHUB_ACTIONS`), and without the typed word `validate`. `render` writes the review tables. |
| `scripts/cosmyx/just/branding.just` | Cosmyx-owned | Recipes `brand-check`, `brand-apply`, `brand-revert`, `brand-sync`, `brand-refresh PATH`, `brand-validate GLOB *FLAGS` (user only), `brand-table`; ends with four `import?` lines, one per sub-task file, so sub-task branches never edit it. |
| `cosmyx-src/branding/manifest/{logos,icons-a-m,icons-n-z,web}.json` | data | The image manifest: 36 + 225 + 294 + 5 = 560 rows, all `missing`, each anchored to an upstream file by its repository-relative path and the SHA-256 of the upstream bytes (`upstream_sha256`). Anchoring is by path plus hash, not by text. |
| `cosmyx-src/branding/overlay/.gitkeep` | data | Empty overlay root; vendored files live at `overlay/<repo-relative path>` (outside `resources/` so CMake does not install them twice). |
| `wiki/cosmyx/branding-assets/{logos,icons-a-m,icons-n-z,web}.md` | docs (generated) | Review tables generated by `just brand-table` from the manifest only; G6 fails when stale. |
| `wiki/cosmyx/branding.md` | docs | The branding workflow: statuses, add/review/validate, what to do after an upstream merge, guards, line-ending rule, local use. |
| `scripts/cosmyx/tests/branding_fixture.py`, `test_branding_{apply,guards,manifest,overlay,recipes}.py`, `test_breaker_branding_engine.py` | test | Unit tests of manifest, guards, overlay, pipeline (idempotent apply, exact revert, clean `git diff --quiet HEAD` after apply plus hide, rollback), a real-tree apply on a scratch copy of the files the committed tables name (`copy_real_tree`), CRLF and LF copies, breaker cases (symlinks, case-only paths). |
| `CHANGELOG.md`, `wiki/decisions/0120-0123*.md` | docs | Line under slot T11a; four decisions. |

Engine behaviour that other branches rely on: `apply` is idempotent (applying a branded tree reverts it first); a failed pre-guard writes nothing; a stage failure or post-guard failure restores the backups at once; `revert` saves state after each file so it can be resumed.

## Rebase risk zones

Checked against `upstream/v2.5.1` by extracting the tag tree, laying this branch's engine, tables and wiki over it, and running `scripts/cosmyx/branding/cli.py check` (and `apply`) on it.

- Manifest hashes: of the 560 rows, 557 match the v2.5.1 upstream bytes (`hash_ok`) and 3 are `gone_in_tag`: `resources/images/menu_add_painted_modifier.svg`, `resources/images/toolbar_painted_modifier.svg`, `resources/images/toolbar_painted_modifier_dark.svg`. These icons belong to the painted-modifier feature that exists in DEV but not in v2.5.1. `check` gives 0 errors and 3 G3 warnings ("upstream file is gone") plus the status warnings. G4 found no new teal icon or branding image in v2.5.1, so no row is missing. Against current DEV all 560 hashes match.
- A rebase onto a release tag therefore needs `just brand-sync` to drop the three rows (it drops a row without a replacement once its file is gone) and `just brand-table`, then commit the manifest and review tables. Do not edit rows by hand.
- Churn: `resources/images` had 116 DEV commits in six months and `resources/web` 114, so G3/G4 drift is expected after any upstream sync (new teal icons, changed hashes). It is a warning on development builds, so builds still run; fix with `just brand-sync` (rows without replacement) or `just brand-refresh <path>` (rows with replacement, which go back to `to-validate`).
- `resources/images/OrcaSlicer*` and `scripts/msix/assets/*` changed 0 times between the merge-base and v2.5.1 (1 and 3 DEV commits in six months), so the logo patterns are stable. If upstream renames or adds a branding image pattern, `LOGO_PATTERNS` in `manifest.py` must be extended.
- The test `test_branding_manifest.CommittedTablesTest.test_every_row_points_at_a_real_file` fails on a v2.5.1 base until the three rows are dropped.
- `.github/actions/cosmyx-prepare/action.yml` is Cosmyx-owned, so it does not conflict, but the workflows calling it are upstream: the `build_orca.yml` hook is documented in the translations branch; the Flatpak hook lives in `build_flatpak.yml` on DEV and in the inline `flatpak:` job of `build_all.yml` on v2.5.1 (see `feat-cosmyx-translations.md`).
- G7 greps tracked files for palette colours and "CosmoSlice": a rebase that pulls an upstream file containing `#8000FF` (it exists upstream in a colour picker palette) needs an `allow_residue` row in `colours.json`.

## Intent to preserve

- Git never carries the branding: every upstream-owned file stays Orca-branded in git; branding exists only in the build tree (or after a deliberate local `just brand-apply`, undone by `just brand-revert`).
- A development build never fails on missing or unvalidated rows or on upstream drift; a release build fails until every row is `validated` and no drift remains.
- Statuses: `missing` (no replacement), `to-validate` (replacement recorded, not approved), `validated`. Only the user moves a row to `validated`, with `just brand-validate <group or glob> --i-am-the-user` in an interactive terminal. **An agent must never run `just brand-validate`, never pass `--i-am-the-user`, never set `COSMYX_BRAND_VALIDATOR`, and never edit a `status` to `validated` in a manifest or in `colours.json`.** A rebase must leave every status exactly as it was; `brand-refresh` correctly sends a changed row back to `to-validate`, which is the policy, not a regression.
- If an upstream icon changed, check that the replacement still fits the new upstream file, then `just brand-refresh <path>`; do not force the old overlay file onto a changed layout without checking it. If upstream removed a file, drop the row with `brand-sync`.
- If upstream moved to a different mechanism (for example a new icon folder), extend discovery (`TEAL_ROOTS`, `LOGO_PATTERNS`) rather than hand-listing rows; the manifest is discovered, not written.
- Line endings never matter: patches and checks run on LF text and keep each file's own ending.
- Keep the step order in the prepare action: graft, branding, `hide` last. The tests and guards assume it.

## Verification

From the repository root, after the rebase:

- `just brand-check` (guards on the tree, writes nothing; expect 0 errors, warnings only for drift and unvalidated rows).
- `just brand-table` followed by `git diff --exit-code wiki/cosmyx/branding-assets` (tables are deterministic; also checked by G6 and `python3 scripts/cosmyx/branding/cli.py render --check`).
- `just brand-sync` on a clean tree, then `git status`: no change means the manifest is in line.
- `just brand-apply` then `just brand-revert`, and `git status --short` is empty (exact revert). Add `python3 scripts/cosmyx/worktree_clean.py hide` / `show` to check the `-dirty` behaviour.
- `PYTHONDONTWRITEBYTECODE=1 COSMYX_TEST_PROFILE=prepare python3 -m unittest discover -s scripts/cosmyx/tests -p 'test_branding_*.py' -t scripts/cosmyx/tests` (the exact line the CI runs on every build leg), then `just test-scripts` for the full set including heavier tests.
- Release behaviour: `COSMYX_BRAND_REF=refs/tags/v0 python3 scripts/cosmyx/branding/cli.py check` must fail while rows are not validated.
- `just decisions`.

## Known pitfalls

- `2b0c26555e` Windows runners check out CRLF (`core.autocrlf`): the engine refused every patched file (G5/G8 "has CRLF line endings") and found every committed table non-canonical (G6). Matching and counting now use LF text; files are written back with their own ending. `ba5ef945d2` the CRLF real-tree test built its copies from an already-CRLF checkout; it now normalises to LF first.
- `a032fcc90f` the prepare action ran every `test_branding_*.py` on each build leg; a test that built the pinned resvg image broke the arm64 Linux leg ("exec format error"). `COSMYX_TEST_PROFILE=prepare` plus `skip_in_prepare` in `branding_fixture.py` make heavy tests skip there; they still run in `just test-scripts` and `cosmyx-checks.yml`. A new branding test needing Docker, network or a long build must carry `skip_in_prepare`.
- `06adfd16a9` revert dropped skip-worktree bits with stderr discarded and G7 called every git failure "not a git checkout"; in a container with an untrusted workspace both hid "dubious ownership" (exit 128). Git's own message is now reported.
- `832dae7e03` (tests `5dceec0a70`) breaker round: a text patch wrote through a symlink outside the tree and patched a case-only different name on macOS/Windows; an unexpected stage exception left the tree branded with no report; a non-integer `allow_residue` count crashed the guards; an interrupted revert could not resume. All fixed (exact-spelling writes only, revert on any exception, error findings instead of exceptions, state saved after each restored file).
- `9d2d565821` the colour and product-name branches both replaced the real-tree test setup at the same lines; the engine now owns one `copy_real_tree` helper. `d1a70f716c` they also rewrote adjacent rows of the "What lives where" table in `branding.md`; the table is now written in its final form here. `cdd2ac9e18` sub-task recipes moved to their own `import?` files so branches never edit `branding.just`.
- The PR body says "560 rows, all missing"; once logos land the count is 561 (one extra row for the Custom bed texture).
- Do not run `just brand-sync`, `brand-refresh` or `brand-validate` on a branded tree: they refuse; revert first.

## Shared files with other branches

- `CHANGELOG.md`: line under slot T11a. Logos use T11b (area `GUI`), colours T11c, and the remaining branding sub-tasks T11d-T11f; never move a marker.
- `wiki/decisions/`: this branch owns 0120-0123; logos 0124-0126, colours 0127-0130 (colours also edits 0123 to add the URL-fragment and character-reference exclusions to the hex rule). Dark mode is decision 0139 in another branch.
- `wiki/cosmyx/branding.md`: edited by every branding branch (logos add a `## Logos` section, colours a `## Colours` section, product name and dark-default their own). Each uses its own section and the "What lives where" table is already in final form, so conflicts should be limited to the same line neighbourhood; resolve by keeping all sections.
- `wiki/cosmyx/branding-assets/*.md` and `cosmyx-src/branding/manifest/*.json`: rewritten by `just brand-sync` / `brand-refresh` on every branch that adds overlay files (logos: `logos.json`; svg-candidates: `icons-*.json`, `web.json`). Always regenerate (`brand-sync`, `brand-table`) instead of merging by hand.
- `scripts/cosmyx/branding/__init__.py` and `guards.py`: colours edits `__init__.py` (hex skip rule, `hex_is_skipped`); the product-name branch adds a plugin module and G8 activation.
- `scripts/cosmyx/tests/branding_fixture.py`, `test_branding_apply.py`: touched by logos (`manifest.refresh` instead of `sync` in `test_a_vendored_logo_applies_and_reverts`) and by sibling branches.
- `.github/actions/cosmyx-prepare/action.yml`: created by translations, edited here; any later prepare step goes above `hide`.
- `scripts/cosmyx/worktree_clean.py` and the justfile `import?` lines: owned by the foundation and translations branches.
