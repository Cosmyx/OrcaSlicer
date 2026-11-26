# feat/cosmyx-raster-images (PR #114)

## Purpose

Raster images (PNG, GIF) cannot be recoloured by the build-time colour stage, so 13 rasters a Cosmyx user sees with a
non-Bambu printer were recoloured by hand by the user and ship as overlays: the 8 Texture displacement tool tip pictures
(`resources/images/texture_displacement/`, `erase.gif` keeps its 14 animation frames) and 5 web images (`homepage/img/i4.png`,
`i5.png`, `model/img/null.png`, `null2.png`, `guide/11/earth.png`). All 13 rows are `validated` (user's request, decision
0121). Kept upstream on purpose, no overlay: the 6 bed plate images (`bed_cool`, `bed_cool_supertack`, `bed_pei_cool` and
their `big_` versions), `resources/textures/displacement/Hex Tiles.png` (also a height map), `resources/web/orca/setup_connection.gif`.
Decision 0214, changelog slot T11g (`### GUI`, after T18 in the file).

## Parent and dependencies

- Parent: `ci/cosmyx-branding-engine` (PR #99). Range: `88ab4cf944` (overlays, rows, test, decision, slot), `723e6ff3ff`
  (changelog PR link), `4fbffcfa64` (rows validated).
- Engine manifest schema, overlay, `brand-sync` / `brand-table`, guards G1-G6.

## Changes

| File | Kind | What the change does |
|---|---|---|
| `cosmyx-src/branding/overlay/resources/images/texture_displacement/*` (8), `overlay/resources/web/...` (5) | data (binary) | The hand-recoloured files, same pixel size as upstream. |
| `cosmyx-src/branding/manifest/icons-n-z.json` (8 rows), `web.json` (5 rows) | data | `kind` `recolour`, `source` `user`, `validated`, `override_sha256`. |
| `wiki/cosmyx/branding-assets/icons-n-z.md`, `web.md` | generated | Regenerated tables. |
| `scripts/cosmyx/tests/test_branding_rasters.py` | test | `RasterOverlayTests`: `RECOLOURED` overlays exist at the upstream size, rows are recolours, `KEPT_UPSTREAM` have no overlay, `erase.gif` keeps its frames. |
| `scripts/cosmyx/tests/test_foundation.py`, decision 0003 | foundation files | `T11g` added to `GUI`. |
| `wiki/decisions/0214-hand-recoloured-rasters.md`, `CHANGELOG.md` | docs | Decision, line under T11g. |

No upstream file is edited in git.

## Rebase risk zones

- An upstream change of one of the 13 images changes its upstream hash: `brand-sync` reports it, and the overlay must be
  redone by hand by the user (never by an agent); the row goes back to `to-validate` through `brand-refresh`.
- The 8 `texture_displacement/` files exist on `v2.5.2` (checked 2026-11-24); on another tag check they exist before
  replaying (a missing upstream file makes the guards fail for those rows), and compare hashes with `brand-sync`.

## Intent to preserve

- Statuses are never changed by an agent; `validated` rows stay `validated` while `override_sha256` is unchanged.
- The kept-upstream list stays without overlay.

## Verification

- `just brand-check` (0 errors), `just brand-table` then no diff, `just test-scripts` (`test_branding_rasters.py`).
- Count: 13 `validated` rows with `source` `user` across `icons-n-z.json` and `web.json`.

## Known pitfalls

- Integration merge: `icons-n-z.json` / `web.json` merge textually with svg-candidates' rows, but the generated tables
  conflict. Take one side, run `just brand-sync` and `just brand-table`, check 571 `validated` rows.

## Shared files with other branches

- `cosmyx-src/branding/manifest/icons-n-z.json`, `web.json` and their tables: svg-candidates owns the SVG rows there.
- `cosmyx-src/branding/overlay/`: one owner per path (logos, svg-candidates, raster-images).
- `CHANGELOG.md` (T11g), `test_foundation.py`, decision 0003.
