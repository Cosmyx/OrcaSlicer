# feat/cosmyx-logos (PR #101)

## Purpose

Ships the CosmoSlice logos in Cosmyx builds: the application icon on every platform, the About banner, the splash screen, the Windows/macOS/MSIX icon sets, the setup guide logo and the Custom printer bed texture. The upstream files keep their OrcaSlicer names and stay untouched in git; the branding engine (PR #99) copies the vendored replacements over them at build time.

Two sources, 34 replacement files in total (37 manifest rows, 3 still missing):

- 22 files vendored byte for byte from the CosmoSlice repository (source `cosmoslice`): `OrcaSlicer.svg`, the `OrcaSlicer_*.png` set, About banner light and dark, splash light and dark, gradient/gray variants, `studio_logo.svg`, the Custom bed texture, etc. Rows record `source_ref` `CosmoSlice@d317226e47` (19 rows, "Added CosmoSlice Logo"), `CosmoSlice@bab368d306` (2 rows, splash) and `CosmoSlice@03d998431f` (1 row, bed texture).
- 12 rasters derived from the vendored SVG master `overlay/resources/images/OrcaSlicer.svg` by `just brand-derive` in a pinned resvg Docker image (source `derived`): multi-size Windows icon (`OrcaSlicer.ico`, 16/32/48/64/128/256 px), the macOS `Icon.icns`, `OrcaSlicer.icns`, `stl.icns` and `gcode.icns`, the four MSIX tiles, the grayscale logo of message dialogs, the 184 px title logo and `web/image/logo.png`.

All 34 rows are `to-validate`: the user has not approved them. Still missing and never to be drawn by an agent: `resources/images/OrcaSlicer_horizontal_light.svg`, `resources/images/OrcaSlicer_horizontal_dark.svg` (Troubleshoot dialog, SVG 214x80 viewBox, logo plus CosmoSlice wordmark) and `resources/web/image/logo2.png` (PNG 339x406, unreferenced upstream). They are asked from the user.

Decisions: 0124 (logos vendored from CosmoSlice), 0125 (rasters derived by a recipe), 0126 (pinned resvg image). Changelog slot T11b (area `GUI`).

## Parent and dependencies

- Parent: `ci/cosmyx-branding-engine` (PR #99), which needs `feat/cosmyx-translations` (#95) and #86. PR #101 targets `DEV` and shows the parents' commits until they merge.
- Depends on the engine's manifest schema, overlay mechanism, `brand-sync` / `brand-refresh`, guards G1-G4 and G6, and the `import?` line for `branding-logos.just` in `branding.just`.
- External source: the CosmoSlice repository (commits `d317226e47`, `bab368d306`, `03d998431f`; the files were copied with `git show <commit>:<path>`). Those commits are not in this repository, so the vendored bytes cannot be regenerated here, only re-copied from CosmoSlice.
- Docker with linux/amd64 containers for `brand-derive*` (resvg 0.48.1 built with `cargo install --locked` in a digest-pinned `rust:1.90-slim-bookworm`, copied into a digest-pinned `python:3.12-slim-bookworm`).
- Upstream files it depends on: the 37 upstream paths of the `logos` rows (list in `wiki/cosmyx/branding-assets/logos.md`): `resources/Icon.icns`; `resources/images/OrcaSlicer*` (`.svg`, `.png`, `.ico`, `.icns`, `_about(_dark).svg`, `_gradient*.svg`, `_gray.svg`, `_horizontal_{light,dark}.svg`, `_192px*.png`, `_154*`, `_128px`, `_32px`, `_64`), `OrcaSlicer-mac_128px.png`, `OrcaSlicer-mac_256px.ico`, `OrcaSlicerTitle.{ico,png}`, `splash_logo(_dark).svg`, `studio_logo.svg`, `stl.icns`, `gcode.icns`; `resources/profiles/Custom/orcaslicer_bed_texture.svg`; `resources/web/image/logo.png` and `logo2.png`; `scripts/msix/assets/{Square150x150Logo,Square44x44Logo,Square44x44Logo.targetsize-44_altform-unplated,StoreLogo}.png`. The `usage` column names the C++ call sites (MainFrame.cpp, AboutDialog.cpp, MsgDialog.cpp, ConfigWizard.cpp, GUI_App.cpp, TroubleshootDialog.cpp, `OrcaSlicer.rc.in`, `MacOSXBundleInfo.plist.in`, `AppxManifest.xml`, `src/CMakeLists.txt`): free text for the reviewer, but the dimensions and ICO layout must still match.

## Changes

| File | Kind | What it does |
|---|---|---|
| `cosmyx-src/branding/overlay/resources/...`, `overlay/scripts/msix/assets/*` | data (binary and SVG) | The 34 vendored or derived replacement files at their upstream repository-relative paths (for example `overlay/resources/images/OrcaSlicer.svg`, `overlay/resources/Icon.icns`, `overlay/scripts/msix/assets/StoreLogo.png`). |
| `cosmyx-src/branding/manifest/logos.json` | data | 37 rows (36 from the engine plus the bed-texture row, which no discovery pattern covers). A vendored row carries `source` `cosmoslice`, `source_ref` `CosmoSlice@<commit>`, `status` `to-validate`, `override_sha256` of the overlay file; a derived row carries `source` `derived` and the `source_ref` text "just brand-derive (scripts/cosmyx/branding/derive/derived-assets.toml) from resources/images/OrcaSlicer.svg". `upstream_sha256` anchors the row to the upstream file it replaces (path plus hash; sizes are the upstream sizes). Three rows stay `missing` with null source. |
| `scripts/cosmyx/branding/derive/derive.py`, `icns.py`, `ico.py`, `raster.py`, `__init__.py` | Cosmyx-owned tool | Port of the CosmoSlice `brand_assets` tool: `write`, `check`, `stable` modes; resvg render, minimal PNG codec, deterministic ICO writer (32-bit BMP entries below 256 px, PNG at 256 px, like upstream), ICNS writer, grayscale variant (ITU-R BT.601 luma in integer arithmetic, alpha kept). `--docker` builds the image (tag is a hash of the Dockerfile) and runs the script inside it as linux/amd64. |
| `scripts/cosmyx/branding/derive/derived-assets.toml` | Cosmyx-owned data | The derivation list: 12 `[[derived]]` tables `{source, output, format (png/ico/icns), size (px or list), grayscale}`. Sizes are those of the upstream file each output replaces. |
| `scripts/cosmyx/branding/derive/Dockerfile` | Cosmyx-owned CI image | Pinned renderer (digests of the Rust and Python images, `resvg 0.48.1 --locked`). Needs no build context (`docker build -`). |
| `scripts/cosmyx/just/branding-logos.just` | Cosmyx-owned | Recipes `brand-derive`, `brand-derive-check`, `brand-derive-stable`. |
| `scripts/cosmyx/tests/test_branding_derive.py` | test | Fake-renderer unit tests of the manifest, the three modes, ICO/ICNS/PNG codecs, grayscale and the Docker command line (run on every OS without Docker). |
| `scripts/cosmyx/tests/test_branding_logos.py` | test | Committed overlay checks: every overlay row has a source and waits for review; derived rows match the derivation list; no overlay file equals an Orca original; raster sizes match the manifest (exceptions: `OrcaSlicer_gradient_narrow.svg` and `studio_logo.svg`, square master, unreferenced upstream); ICO layout matches upstream; grayscale logo has no colour; every derived output equals a fresh render in the pinned image (skipped with the reason where linux/amd64 containers cannot run, and in the prepare action). |
| `scripts/cosmyx/tests/test_branding_apply.py` | test (edited) | `test_a_vendored_logo_applies_and_reverts` now calls `manifest.refresh(self.root, target)` instead of `manifest.sync` because the committed row for `OrcaSlicer.svg` already has a replacement. |
| `wiki/cosmyx/branding-assets/logos.md`, `wiki/cosmyx/branding.md`, `wiki/decisions/0124-0126*.md` | docs | Regenerated review table, a `## Logos` section (sources, derive workflow, assets still to provide), three decisions. |
| `CHANGELOG.md` | docs | One line under slot T11b. |

No upstream file is edited in git.

## Rebase risk zones

Checked on a v2.5.1 tree with this branch's engine, tables and overlay laid over it.

- All 37 `upstream_sha256` values of `logos.json` match the v2.5.1 bytes (37/37 `hash_ok`) and match current DEV, so G3 does not fire for logos. `resources/images/OrcaSlicer*` and `scripts/msix/assets` were not touched between the merge-base (65aab6bcf7) and v2.5.1.
- `brand-apply` on the v2.5.1 tree applies 34 overlay files with 0 errors and `brand-revert` restores 34 files exactly. `brand-check` on v2.5.1: 0 errors; the only G3 warnings are the three painted-modifier icon rows of the other tables (not logos).
- Remaining logo drift risks if upstream moves: a changed upstream hash (G3 warning on dev builds, error on release) when upstream redraws or resizes a logo; a renamed or new `OrcaSlicer_*` variant (G4: needs a new row, `just brand-sync`); a change of ICO layout or raster size, which fails `test_ico_layout_matches_upstream` / `test_sizes_match_the_manifest`; upstream adding the Troubleshoot or `logo2.png` content (rows are `missing`, so nothing is applied, but sync refreshes their hashes).
- Because the upstream originals are replaced, a changed upstream logo is silently overwritten by the Cosmyx one: check what changed upstream with `git diff <old>..<new> -- <path>` before `brand-refresh` (it also sends the row back to `to-validate`).
- Rendering tooling: `Dockerfile` digests can disappear from registries; `derive` bytes depend on resvg 0.48.1. A fresh render on the arm64 Linux leg or a machine without amd64 emulation is skipped, never failed (test `73d7679e4f`).
- The vendored CosmoSlice files do not depend on upstream and never conflict.

## Intent to preserve

- The branded app shows CosmoSlice logos everywhere upstream shows the Orca ones, with the upstream file names, sizes and ICO/ICNS layouts, so no C++ or CMake change is needed.
- Vendored files are byte-identical copies from the cited CosmoSlice commit; derived files are only ever produced by `just brand-derive` from the master SVG, never edited by hand; assets are never drawn, generated, downloaded or approximated by an agent. Missing assets are requested from the user with exact file, format, size and use.
- Statuses: every logo row is `to-validate` and must stay so. **An agent must never run `just brand-validate`, never pass `--i-am-the-user`, and never edit a row's `status` to `validated`.** Only the user does, in their own terminal (for example `just brand-validate logos --i-am-the-user`). After `brand-refresh` a row correctly returns to `to-validate`. A rebase must not change any `status`, `source`, `source_ref` or `override_sha256` except through the recipes.
- If upstream rewrote or restructured a logo (new size, new variant, renamed file), re-anchor the row with `just brand-refresh <path>` or `just brand-sync` rather than forcing the old overlay onto the new upstream file; then ask the user to revalidate and, if the new layout needs a new asset, ask for it.
- If the master SVG or the derivation list changes, run `just brand-derive` (needs Docker), then `just brand-refresh <path>` for each rewritten output.
- Derived rows stay `source: derived`; vendored rows stay `source: cosmoslice` with their commit.

## Verification

After the rebase, from the repository root:

- `just brand-check` (0 errors expected).
- `just brand-table` then `git diff --exit-code wiki/cosmyx/branding-assets/logos.md` (generated table in sync; G6 checks it too).
- `just brand-derive-check` (needs Docker, linux/amd64): fails if a committed derived file differs from a fresh render. `just brand-derive-stable` renders twice and compares.
- `just brand-apply`, inspect `build/cosmyx/branding-report.json` (34 overlay files), then `just brand-revert`; `git status --short` must be empty afterwards.
- `PYTHONDONTWRITEBYTECODE=1 COSMYX_TEST_PROFILE=prepare python3 -m unittest discover -s scripts/cosmyx/tests -p 'test_branding_*.py' -t scripts/cosmyx/tests` (what the CI runs per build leg), then `just test-scripts` for the fresh-render test on a machine with Docker.
- Manifest sanity: every row with an overlay is `to-validate` (or `validated` exactly as it was before the rebase) and exactly three rows are `missing`.
- `just decisions`.

## Known pitfalls

- `73d7679e4f` on the arm64 Linux build leg the fresh-render test built the pinned image and died with "exec format error" (the daemon was not amd64). The test now starts the digest-pinned base image once and skips with the daemon's reason; it also carries `skip_in_prepare`.
- `c2aff26fbd` the overlay test listed tracked upstream images with `git ls-files` and failed with a bare `CalledProcessError` (exit 128) in the Flatpak container (dubious ownership); it now reports git's message.
- `a5d94dd315` ICO details: the upstream icon has 16/32/48/64/128/256 entries (not the 16/24/32/48/64/256 set first proposed); `OrcaSlicer_154_title.png` is 184 px like upstream.
- `OrcaSlicer_gradient_narrow.svg` and `studio_logo.svg` have a narrower upstream aspect ratio than the square CosmoSlice master; both are unreferenced upstream and listed as accepted exceptions in the size test until the reviewer accepts or replaces them.
- The PR body lists older shas (`26aa021130` ...); the live ones are `259da417f2`, `06e7b901da`, `bf94f54c43`, `a5d94dd315`, `02dbf88cf9`, `54d596c005`, `c2aff26fbd`, `73d7679e4f`.
- The first build on a machine compiles resvg (several minutes under emulation on arm64).
- Binary overlay files are tracked as binary by git; with `* text=auto eol=lf` Git does not rewrite them, but a CRLF checkout of SVG overlays is handled by LF-based SVG hashing in the engine (do not hash them yourself).

## Shared files with other branches

- `cosmyx-src/branding/manifest/logos.json` and `wiki/cosmyx/branding-assets/logos.md`: created by the engine (all `missing`), rewritten here; later branches that add missing logos regenerate with `brand-sync` / `brand-table`, never merge by hand.
- `cosmyx-src/branding/overlay/`: shared tree with the SVG-candidates branch (overlay icons for `icons-*` / `web` groups); a path must have one owner, G2 fails on an orphan overlay.
- `wiki/cosmyx/branding.md`: this branch adds the `## Logos` section; colours adds `## Colours`; others add their own. Keep all sections on conflict.
- `wiki/decisions/`: 0124-0126 are this branch's numbers (engine 0120-0123, colours 0127-0130).
- `CHANGELOG.md`: slot T11b only.
- `scripts/cosmyx/tests/test_branding_apply.py`: also edited by sibling branches around the real-tree test; the `manifest.refresh` change must survive.
- `scripts/cosmyx/just/branding-logos.just`: own file, loaded by the `import?` line in `branding.just`; no shared edit.
- `.github/workflows/cosmyx-checks.yml`: its Linux leg is where the fresh-render test runs; no edit here.
