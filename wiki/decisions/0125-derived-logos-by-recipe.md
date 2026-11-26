# 0125. Raster logos are derived from the SVG master by a recipe

## Status

Accepted.

## Context

Several branding rasters have no CosmoSlice version at the right sizes: the
multi-size Windows icon (CosmoSlice ships a single 154 px entry), the four
MSIX tiles and the macOS app icon (`.icns`). The user approved deriving them from the vendored
CosmoSlice master `resources/images/OrcaSlicer.svg`. Derived assets are only
ever produced by a recipe, never by hand.

## Decision

- The CosmoSlice derivation tool (`scripts/brand_assets`) is ported to
  `scripts/cosmyx/branding/derive/`: `derive.py`, `icns.py` and
  `derived-assets.toml`, plus `ico.py` (multi-size ICO) and `raster.py`
  (minimal PNG decoder and encoder, for the grayscale variant and the ICO
  bitmaps).
- `derived-assets.toml` lists each output with its source, format and size.
  Sizes are those of the upstream file each output replaces, so a replacement
  keeps its dimensions: `OrcaSlicer.ico` holds 16, 32, 48, 64, 128 and 256 px
  like upstream (not the 16/24/32/48/64/256 set first proposed).
- The ICO mirrors the upstream layout: 32-bit BMP entries below 256 px (resource
  compiler, NSIS and old shells read them), a PNG entry at 256 px.
- A `grayscale` output is a real grayscale: every pixel set to its ITU-R
  BT.601 luma in integer arithmetic, alpha kept.
- `just brand-derive` rewrites the outputs whose bytes changed;
  `just brand-derive-check` fails on a stale output and
  `just brand-derive-stable` renders twice and compares. Rewritten outputs are
  then refreshed with `just brand-refresh PATH` and go back to `to-validate`.
  Derived rows have source `derived`.

## Consequences

- A change of the master SVG is one recipe away from every raster.
- The `.icns` file comes out byte-identical to the one CosmoSlice derived with the same tool and image.
- Removing it: delete `scripts/cosmyx/branding/derive/` and the three recipes;
  the derived overlay files would then have to come from the user.
