# 0214. Hand-recoloured raster images, and the ones that keep their upstream look

## Status

Accepted.

## Context

The build-time recolouring (decision 0120) maps the Orca teal colours to the
Cosmyx violets in SVG and text sources. Raster images (PNG, GIF) cannot be
recoloured that way: their teal is anti-aliased and blended into shading. An
audit of the rasters without an overlay found 21 that a Cosmyx user sees with
a non-Bambu printer. The others only show with a Bambu printer, are never
loaded, or only serve the Flatpak packaging.

## Decision

- 13 of them are recoloured by hand by the user and added as overlays under
  `cosmyx-src/branding/overlay/`, with `kind` `recolour` and status
  `validated`: the user recoloured them and asked for them to be validated
  with this change (decision 0121):
  - the 8 tool tip pictures of the Texture displacement tool,
    `resources/images/texture_displacement/` (`erase.gif` keeps its 14
    animation frames);
  - 5 web page images: the home tab `New Project` and `Open Project` buttons
    (`i4.png`, `i5.png`), the empty project tab in light and dark mode
    (`null.png`, `null2.png`), and the setup wizard region page
    (`earth.png`).
- These keep their upstream look on purpose and get no overlay:
  - the 6 bed plate images (`bed_cool`, `bed_cool_supertack`, `bed_pei_cool`
    and their `big_` versions): their colours show the real plate surfaces;
  - `resources/textures/displacement/Hex Tiles.png`: it is also a height map,
    so recolouring it could change the displaced surface;
  - `resources/web/orca/setup_connection.gif`.
- Every overlay has the same pixel size as the upstream file.
  `scripts/cosmyx/tests/test_branding_rasters.py` pins the 13 overlays,
  their sizes, and the absence of an overlay for the kept images.

## Consequences

- When upstream replaces one of these images, `just brand-sync` reports the
  new upstream hash and the overlay must be redone by hand.
- Removing this decision means deleting the 13 overlay files and running
  `just brand-sync`, which drops their rows; the upstream teal images then ship
  again.
