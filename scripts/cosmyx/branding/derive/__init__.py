"""Branding derivation (T11b): raster files rendered from a vendored SVG master.

- `derive`: the command line and the render pipeline (`write`, `check`, `stable`), driven by
  `derived-assets.toml` next to it.
- `icns`: deterministic Apple ICNS writer and parser.
- `ico`: deterministic Windows ICO writer and parser.
- `raster`: minimal PNG decoder and encoder, for the grayscale variant and the ICO bitmaps.

Rendering needs the pinned resvg of the `Dockerfile` in this folder: `just brand-derive` runs it there.
Ported from the CosmoSlice brand_assets tool (decisions 0124-0126). Standard library only.
"""
