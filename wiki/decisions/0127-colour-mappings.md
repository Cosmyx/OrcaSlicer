# 0127. Colour mappings, palette and their validation

## Status

Accepted.

## Context

The Cosmyx build replaces the Orca teal with violets. The user gave four
colours: `#8000FF` (brand), `#A472F5` (brand on the dark screen `#1C1C1F`),
`#382D43` (dark) and `#B4B9DD` (lavender). Orca uses more teal roles than
that (hover, pressed, tints, dark variants, off-by-one shades), and only the
user approves what ships.

## Decision

- `cosmyx-src/branding/colours.json` holds the `palette` (the user's four
  colours plus the derived `#DFBFFF`, `#F2E6FF` and `#393444`) and one
  `mappings` row per Orca colour: `{from, to, role, source, status}`.
- `source` is `user` when the target and its role come from the user
  (`#009688`, `#00675B`, `#223C3C`, and the lavender for `#52C7B8` and
  `#4DB6AC`), `derived` otherwise. Every row starts `to-validate`, the user's
  own colours included: the user flips a row to `validated` by editing
  `colours.json`; agents never do.
- Derived targets come from the user's colours: tints are `#8000FF` blended
  over white (25% gives `#DFBFFF`, 10% gives `#F2E6FF`), hovers swap the two
  brand violets, pressed and off-by-one shades (`#00897B`, `#009687`,
  `#009789`, `#009C88`, `#00BFBF`, `#007A74`) take the brand, bright accents
  take `#A472F5` or the lavender.
- `to` must be a palette colour, `from` must be unique and not ignored, and
  both are uppercase `#RRGGBB`. Unvalidated mappings warn on development
  builds and fail release builds, like the image rows (decision 0121).

## Consequences

- Changing a colour is one edit of a `to` cell (or of the palette and its
  rows), then the wiki table regenerated from `just brand-colour-candidates`.
- Removing the mappings: empty `mappings`; the literal rows then have nothing
  to regenerate from and the build keeps the Orca colours.
