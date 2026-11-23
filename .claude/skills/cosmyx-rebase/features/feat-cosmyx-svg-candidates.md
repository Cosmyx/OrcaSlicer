# feat/cosmyx-svg-candidates (PR #110)

## Purpose

About 520 SVG icons under `resources/images` and `resources/web` draw the Orca teal. The build-time colour stage (parent
branch) only rewrites C++ and web sources, so these icons would stay teal. This branch adds the tool that proposes one
recoloured violet SVG per icon, an HTML review sheet to look at them before and after on light and dark backgrounds, and the
command that moves approved ones into the branding overlay. It also contains the result: all 524 recolour icons accepted
into `cosmyx-src/branding/overlay/` as `to-validate` rows (the user reviewed the three sheets and approved every candidate
on 2026-11-19). Marking them `validated` remains the user's own `just brand-validate` command (decision 0121); an agent
never does it. Decision 0131. At release time `missing` or `to-validate` rows make the build fail.

## Parent and dependencies

- Parent: `feat/cosmyx-colours` (PR #102, stacked; the PR body says "Depends on #102"). Own range
  `origin/feat/cosmyx-colours..origin/feat/cosmyx-svg-candidates` = 8 commits: `f8df299241` (tool), `3d6302b2c6` (tests),
  `992e44edd3` (docs, decision 0131, changelog line), `a3968541fa` (docs, hover teal mapping), `21f3f00159`, `146a51ec48`,
  `3bb5fae946` (accept icons-a-m, icons-n-z, web), `5404934bbb` (docs: user approval).
- Chain below the parent (not in the range, must be rebased first): the branding engine `ci/cosmyx-branding-engine`
  (guards G1-G8, manifest, overlay, `just brand-*`), the colour stage with `colours.json`, and the foundation.
- Reads from other branches' artifacts: `cosmyx-src/branding/colours.json` (only `validated` mappings, 24 mappings, including
  `#33ABA1 -> #A472F5` for the one-layer hover icons), the manifests `cosmyx-src/branding/manifest/{icons-a-m,icons-n-z,web}.json`,
  and the `BitmapCache.cpp` colour maps (light map and the dark map with the Cosmyx snippet) which the review sheets
  simulate.
- Upstream artifacts it depends on: the 524 upstream SVG files themselves (hash-anchored), and `src/slic3r/GUI/BitmapCache.cpp`
  declarations parsed by the review step. No upstream code is called and no upstream file is edited.

## Changes

| File | Kind | What the change does |
|---|---|---|
| `scripts/cosmyx/branding/candidates.py` | Cosmyx-owned (tooling) | Three commands: `generate` writes a recoloured candidate per `recolour` manifest row with no overlay yet to `build/cosmyx/candidates/` (untracked) and an index; `review` writes self-contained HTML sheets per group to `build/cosmyx/review/` (before and after on `#FFFFFF` with the light map and on `#1C1C1F` with the dark map, images as `<img>` data URIs); `accept PATTERN` copies reviewed candidates into the overlay and records each row as `source: candidate`, `status: to-validate`, `source_ref: just brand-candidates, colours.json sha256 <12 hex>`. The rewrite applies only validated mappings, uppercase output, alpha kept, only in attribute values, `style` attributes and `<style>` declaration blocks; never in `id`/`href`, `url(...)`, URL fragments, character references, comments, CDATA or text. `accept` is all or nothing and refuses stale input (changed `colours.json`, changed upstream file, edited candidate) or a row that already has an overlay. |
| `scripts/cosmyx/just/branding-candidates.just` | Cosmyx-owned (recipes) | `brand-candidates`, `brand-review`, `brand-accept GLOB`. Imported by `branding.just`. |
| `scripts/cosmyx/tests/test_branding_candidates.py` | test | `RecolourSvgTest`, `ColourMapTest`, `CandidatesTreeTest`, `RealTreeCandidatesTest` (see Verification). |
| `cosmyx-src/branding/overlay/resources/images/*.svg`, `.../resources/web/**/*.svg` | data (vendored) | 524 recoloured copies of upstream SVGs at the upstream path (e.g. `overlay/resources/images/toolbar_move.svg`, `toolbar_move_dark.svg`, `overlay/resources/web/guide/0/loading.svg`). Overlay sits outside `resources/` so CMake does not install it twice; the build copies each over the upstream file. |
| `cosmyx-src/branding/manifest/icons-a-m.json`, `icons-n-z.json`, `web.json` | data | Schema: `{path, format, size, usage, kind: "recolour", source: "candidate", source_ref, status: "to-validate", upstream_sha256, override_sha256}`. Rows anchor to upstream by `path` and `upstream_sha256` (hash of the upstream file when the overlay was made); `override_sha256` is the hash of the overlay file. Rows are sorted and canonical (guard G6). |
| `wiki/cosmyx/branding-assets/icons-a-m.md`, `icons-n-z.md`, `web.md` | data (generated docs) | Review tables regenerated from the manifest by `just brand-table`; guard G6 fails when stale. |
| `wiki/cosmyx/branding.md` | docs | Adds the "SVG candidates" section. |
| `wiki/decisions/0131-svg-recolour-candidates.md` | docs | The decision. |
| `CHANGELOG.md` | data | Line under `<!-- cosmyx-slot: T11d -->` in `### GUI`. |

No upstream file is modified: nothing to hook.

## Rebase risk zones

The only upstream surface is the set of 524 SVG files. Checked with the recorded `upstream_sha256` against `git show
<rev>:<path>`:

| Check | origin/DEV | upstream/v2.5.1 |
|---|---|---|
| Rows whose upstream hash equals the recorded one (guard G3 passes) | 524 of 524 | 521 of 524 |
| Rows whose upstream file is absent | 0 | 3: `resources/images/menu_add_painted_modifier.svg`, `resources/images/toolbar_painted_modifier.svg`, `resources/images/toolbar_painted_modifier_dark.svg` (added to DEV after the release; `git diff --name-status origin/DEV upstream/v2.5.1` shows them as deletions) |
| Rows whose upstream file exists with a different hash | 0 | 0 |
| Teal SVGs without a manifest row (guard G4) | 0 (`just brand-check`); a rough scan on mapping sources also hits `canvas_menu_dark_hover.svg`, `canvas_section_dark_hover.svg`, `canvas_zoom_dark_hover.svg`, but they are outside the teal family G4 uses | 0, confirmed by `just brand-check` on the v2.5.1 pass |
| SVG count under `resources/images` and `resources/web` | 1201 | 1198 |

Upstream churn: 116 DEV commits since 2026-01-01 touch `resources/**/*.svg`. Colours engine files (`BitmapCache.cpp`)
are identical in DEV and v2.5.1 (empty diff), and `icons-a-m.json` is Cosmyx-owned.

A rebase onto v2.5.1 therefore needs: remove the 3 rows and their 3 overlay files, regenerate the review tables, no other
icon change. The hash anchors make any upstream change to an SVG loud (G3).

## Intent to preserve

- Every teal icon has a violet overlay file that equals the upstream file with only the validated colour mappings replaced
  (hex form uppercase), and nothing else changed: no change to ids, hrefs, `url()`, fragments, text, comments.
- No candidate uses an unvalidated mapping. The user reviews sheets before accepting; accepted rows stay `to-validate` until the
  user runs `just brand-validate`. An agent must never run `brand-validate` or `--i-am-the-user`.
- Rows record both the upstream hash and the overlay hash, so a changed upstream icon cannot silently ship a stale recolour.
- If an upstream SVG changed (G3 hash mismatch), do not edit the overlay by hand: regenerate the file from the new upstream
  file with the same rewrite, either by resetting that row to `missing` and running `just brand-candidates`, review, then
  `just brand-accept <path>`, or by `just brand-refresh <path>` after checking that the replacement still fits, which sends the
  row back to `to-validate`. Review again with `just brand-review` when the colour mapping changes.
- If upstream adds a teal SVG (G4): `just brand-sync`, then candidates and accept as above.
- If upstream removes or renames an icon: delete its overlay file and row.
- If upstream changes the way icons are coloured (`BitmapCache.cpp` maps), the review sheets must be checked again because
  they replicate those maps.

## Verification

- `just test-scripts` (workflow `Cosmyx checks`, three OSes) runs `scripts/cosmyx/tests/test_branding_candidates.py`:
  `RecolourSvgTest` (attribute/style/`<style>` rewrite, counts, 8-digit colours keep alpha, id/href/url/base64/text/comments
  untouched, only validated mappings), `ColourMapTest` (parse light and dark maps, branded source, map order, missing
  declaration refused), `CandidatesTreeTest` (generate writes recolour candidates only, G4 report, stale candidates emptied,
  refuses a branded tree, self-contained review sheets, accept records `to-validate` candidate rows, glob and no match,
  all or nothing, stale inputs refused, row with an overlay refused, CLI), `RealTreeCandidatesTest.test_every_teal_svg_is_accepted`
  (no teal SVG left to propose) and `test_generate_and_review_run_clean` (runs generate over every real icon on a scratch copy
  with the accepted rows reset).
- `just brand-check` runs every guard G1-G8 and writes nothing: G1 (overlay hash), G2 (overlay has a row), G3 (upstream hash),
  G4 (no unlisted teal), G6 (tables canonical and review tables up to date). It should be clean except for `to-validate`
  warnings on development builds.
- Manual: `just brand-apply`, build, look at the toolbar and web pages in light and dark, then `just brand-revert`.
- GUI goldens (T16) are not on this branch.

## Known pitfalls

- `a3968541fa`: decision 0131 once said `#33ABA1` (hover teal of the four `one_layer_*_hover` icons) had no mapping and no
  candidate. The user mapped it to `#A472F5` (decision 0127, parent branch), so all 524 icons are covered. The final state
  of the real-tree test (`5404934bbb`) checks that no teal SVG is left to propose, so a new mapping hole fails the test.
- The accept step is all or nothing and refuses stale candidates; the three accept commits are per group. Reverting them means
  reverting `5404934bbb` too.
- Overlay SVGs for icons present in DEV but not in the release (the three `painted_modifier` icons) trip guard G3 on a
  v2.5.1 base: a warning on development builds, an error on release builds (G3 severity follows the build ref, not the
  base), and `test_every_row_points_at_a_real_file` fails on every build. Drop them with their rows: `git rm` the overlay
  file, `just brand-refresh <path>` (override becomes null, row `missing`), then `just brand-sync` (drops it) and
  `just brand-table`. `brand-sync` alone never drops a row that still has an `override_sha256`.
- Windows checkouts use CRLF: the engine reads text as LF (fixes `2b0c26555e`, `c9a1d85718` on the parent branches); an overlay
  file that is committed with CRLF changes the recorded hash.
- v2.5.1 pass (copy tip `e3f21df2ea`): restacking on the adapted colours conflicted in the icons-a-m and icons-n-z accept commits (`icons-*.json`, `icons-*.md`). Resolution per commit: take the replayed side of the manifest and table, `git rm` the painted-modifier overlay files of that group, `just brand-refresh <path>`, `just brand-sync`, `just brand-table`, `git add -A`, continue. Result: 521 overlay files, all `to-validate`.
- v2.5.2 pass (copy tip `715c60a6f7`): `rerere` replayed the manifest and table conflicts of the accept commits, but not the `git rm` of the three painted-modifier overlays (rerere records text resolutions only), so `brand-check` failed with three G2 orphan overlays. Fixed inside the accept commits: one `git commit --fixup=<accept commit>` per commit with the `git rm`, then `GIT_SEQUENCE_EDITOR=true git rebase -i --autosquash <colours tip>`. The resulting `cosmyx-src/` and `wiki/` equal the v2.5.1 copy.

## Shared files with other branches

- `cosmyx-src/branding/manifest/*.json` and `wiki/cosmyx/branding-assets/*.md`: shared with the colours branch (creates the
  rows as `missing`), the logos branch (`logos.json`, `logos.md`), and the product-name branch (none, it uses its own folder).
  Rebase conflicts on manifest rows are resolved by regenerating with `just brand-sync` and `just brand-table`, never by hand.
- `wiki/cosmyx/branding.md` (also edited by colours, logos, product-name), `CHANGELOG.md` (slot T11d), `wiki/decisions/`
  (0131 sits next to 0127-0130 from colours and 0132-0135 from product-name), `justfile` and `scripts/cosmyx/just/branding.just`
  (imports `branding-candidates.just`), `scripts/cosmyx/branding/` engine package.
- `cosmyx-src/branding/colours.json` is read-only for this branch but its hash is embedded in each row's `source_ref`;
  a change of that file marks candidates stale for any re-accept.
