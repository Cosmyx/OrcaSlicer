# 0131. SVG recolour candidates, reviewed before they reach the overlay

## Status

Accepted.

## Context

About 520 SVG icons under `resources/images` and `resources/web` draw the
Orca teal. The colour stage (decision 0128) only rewrites C++ and web
sources at build time, so these icons stay teal unless an overlay file
replaces them (decision 0120). Hand-editing hundreds of files cannot be
reviewed, and the user approves every image that ships (decision 0121).

## Decision

- `scripts/cosmyx/branding/candidates.py` proposes one recoloured SVG per
  `recolour` manifest row of `icons-a-m`, `icons-n-z` and `web` that has no
  overlay yet. It uses only the `validated` mappings of `colours.json`, and
  rewrites them with the hex rule of decisions 0123 and 0128 (shared
  `hex_is_skipped`, uppercase output, alpha kept) only in attribute values,
  `style` attributes and the declaration blocks of `<style>` elements.
  `id` and `href` attributes, `url(...)`, URL fragments, character
  references, comments, CDATA and text content never change.
- `just brand-candidates` writes the candidates and an index to
  `build/cosmyx/candidates/` (never tracked). Teal left in a file (a colour
  without a validated mapping) is reported per file; a teal SVG without a
  manifest row (what guard G4 reports) is reported and skipped until
  `just brand-sync`.
- `just brand-review` writes self-contained HTML sheets, one per group, to
  `build/cosmyx/review/`: before and after on `#FFFFFF` with the light map
  of `BitmapCache.cpp`, and on `#1C1C1F` with its dark map, both read from
  the tree and branded as the build brands them (snippets, then the hex
  rewrite). Images are `<img>` tags with data URIs only.
- `just brand-accept <group or glob>` copies the reviewed candidates into
  the overlay and records each row as source `candidate`, status
  `to-validate`, with the `colours.json` hash in `source_ref`. It is all or
  nothing and refuses a stale candidate (changed `colours.json` or upstream
  file, edited candidate) and a row that already has an overlay. Agents
  never run it on the real tables before the user has reviewed the sheets;
  accepted rows are committed per group. Only the user validates them.
- The recipes live in `scripts/cosmyx/just/branding-candidates.just`
  (decision 0120).

## Consequences

- An icon turns violet in the product only once its candidate is accepted;
  until then it keeps its teal, and release builds fail on its `missing`
  row.
- A teal shade without a mapping produces no candidate: it needs a mapping
  in `colours.json`, validated by the user, first. `#33ABA1`, the hover
  teal of the four `one_layer_*_hover` icons, was the only one; the user
  mapped it to `#A472F5` (decision 0127), so every recolour icon now gets a
  candidate.
- The user reviewed the `icons-a-m`, `icons-n-z` and `web` review sheets
  and approved every candidate on 2026-11-19. All 524 candidates were
  accepted, one commit per group, as `to-validate` rows. The user validated
  all 524 on 2026-11-24, and they are recorded as `validated`.
- Removing it: delete `candidates.py` and its recipe file; overlay files
  are then written by hand and recorded with `just brand-sync`.
