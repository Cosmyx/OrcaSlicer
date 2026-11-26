# 0129. What teal may stay after the build

## Status

Accepted.

## Context

After the rewrite, some teal is not branding: colour picker swatches,
filament swatches, cyan highlights drawn on the 3D scene, test data,
vendored third-party pages. The build must still catch any teal nobody
decided about, including a new shade upstream adds.

## Decision

- After apply, guard G5 fails on any teal left in the scopes: hex colours
  (engine), colour tuples and `0xRRGGBB` integers in the teal family, and any
  mapped colour even outside the family (`#283232` is too grey for the
  family).
- A leftover is allowed only by an `allow_residue` row `{file, match, count,
  reason}` with its exact count (`match` is `#RRGGBB`, `rgb(R, G, B)` or
  `0xRRGGBB`). The 39 rows cover the colour picker palettes and their test,
  filament swatches, `ColorRGB(A)::CYAN()`, the 3D canvas and UV editor
  highlights, an unused test stylesheet and a commented-out palette. Two more
  rows permit the `#8000FF` upstream already has (guard G7).
- The vendored Elegoo printer page and xterm are excluded from the scopes.
  `#FEFFFF` (near white, inside the hue range) is in `ignore`.

## Consequences

- A new teal colour upstream fails the build until it gets a mapping or an
  `allow_residue` row with its reason.
- Removing an allowance: delete its row, then map the colour.
