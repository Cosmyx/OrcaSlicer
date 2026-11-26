# Cosmyx branding

The Cosmyx build ships the CosmoSlice look (logos, violet colours, product
name, dark mode) while the git tree stays OrcaSlicer: nothing upstream owns is
edited in git. Every build applies the branding to its checked-out tree, from
the tables under `cosmyx-src/branding/`, and a local checkout keeps the Orca
branding unless you run `just brand-apply`.

## What lives where

| Path | What it holds |
|------|---------------|
| `cosmyx-src/branding/manifest/<group>.json` | One row per upstream image the build replaces. Groups: `logos`, `icons-a-m`, `icons-n-z`, `web`. |
| `cosmyx-src/branding/overlay/<path>` | The vendored replacement for the upstream file at `<path>` (for example `overlay/resources/images/OrcaSlicer.svg`). |
| `cosmyx-src/branding/colours.json` | The colour palette, mappings, literal rows, snippets, scopes and allowed residue (see [Colours](#colours)). |
| `cosmyx-src/branding/product-name/` | The product name: `patches.json`, `rename.json`, `allowlist.json` (see [Product name](#product-name)). |
| `wiki/cosmyx/branding-assets/<group>.md` | The review tables, generated from the manifest. |
| `scripts/cosmyx/branding/` | The engine: guards, apply, revert, sync. |

The overlay sits outside `resources/` because CMake installs that folder
whole: a file kept there would ship twice.

## Statuses

Each manifest row has one status:

- `missing`: no replacement yet. The build keeps the OrcaSlicer file.
- `to-validate`: a replacement is in the overlay and applied, but you have not
  approved it yet.
- `validated`: you looked at the replacement and approved it.

Development builds (pull requests, `DEV`, `MIXED`, local runs) apply whatever
is there and only warn about `missing` and `to-validate` rows. Release builds
(`release/*` branches and tags) fail until every row is `validated`.

## Workflow

1. **Add or change a replacement.** Put the file in
   `cosmyx-src/branding/overlay/` at the upstream path, then run
   `just brand-sync`. The row records the file's hash and becomes
   `to-validate`. Commit the overlay file, the manifest and the review tables
   together.
2. **Review.** Read `wiki/cosmyx/branding-assets/<group>.md` for what is
   pending, and look at the images themselves. To see them in the app, run
   `just brand-apply`, build, look, then `just brand-revert`.
3. **Validate (you only).** In your own terminal:

   ```text
   just brand-validate logos --i-am-the-user
   ```

   The argument is a group name or a path glob
   (`'resources/images/OrcaSlicer_*'`). The command lists the rows and asks
   you to type `validate`. It refuses without the flag, without a terminal and
   in CI. Agents never run it: validation is your approval, and an agent's
   approval is not one.
4. **Check.** `just brand-check` runs every guard and writes nothing.

## Logos

The `logos` rows come from two sources (decisions 0124-0126):

- **Vendored from CosmoSlice** (source `cosmoslice`): the files CosmoSlice
  already ships under the OrcaSlicer names, copied byte for byte. The
  `source_ref` names the CosmoSlice commit.
- **Derived** (source `derived`): rasters rendered from the vendored master
  `overlay/resources/images/OrcaSlicer.svg`, as listed in
  `scripts/cosmyx/branding/derive/derived-assets.toml`: the multi-size Windows
  icon, the macOS `.icns` files, the four MSIX tiles, the grayscale and title
  logos, and the web header logo. Never edit one by hand. To change them,
  change the master or the list, then:

  ```text
  just brand-derive              # re-render, rewrite only what changed
  just brand-refresh <path>      # for each rewritten file: back to to-validate
  ```

  `just brand-derive-check` fails when a committed output differs from a
  fresh render, `just brand-derive-stable` renders twice and compares. They
  render in the pinned resvg image (`scripts/cosmyx/branding/derive/Dockerfile`),
  so they need Docker with Linux containers.

Still missing, to be provided (never drawn here):

- `resources/images/OrcaSlicer_horizontal_light.svg` and
  `OrcaSlicer_horizontal_dark.svg`: SVG, 214x80 viewBox, the logo and the
  CosmoSlice wordmark for light and dark backgrounds (Troubleshoot dialog).
- `resources/web/image/logo2.png`: PNG 339x406, unreferenced upstream.

## After an upstream merge

Upstream may add, change or remove images. The build reports it (warnings on
development builds, errors on release builds):

- a new teal icon or a new `OrcaSlicer*` image without a row (G4), or a
  changed or removed file whose row has no replacement yet (G3): run
  `just brand-sync` and commit the result;
- a changed upstream file under a replacement (G3): check that the
  replacement still fits the new upstream file, then run
  `just brand-refresh <path>`. The row goes back to `to-validate`, so it needs
  your validation again.

If you change an overlay file after it was recorded, the hash no longer
matches (G1) and the build fails: run `just brand-refresh <path>` and validate
it again.

## Guards

The build checks the tables before it writes anything and the tree after:

| Guard | Checks |
|-------|--------|
| G1 | Every replacement has its overlay file with the recorded hash, and the branded file carries it. |
| G2 | Every overlay file has a manifest row. |
| G3 | The upstream file still exists with the recorded hash. |
| G4 | Every teal SVG under `resources/images` and `resources/web`, and every branding image, has a row. |
| G5 | Colour rewrites match their exact counts, and no teal is left in the colour scopes unless allow-listed. |
| G6 | The tables are valid, sorted and canonical, and the review tables are up to date. |
| G7 | No CosmoSlice colour or name is committed in an upstream-owned file. |
| G8 | Product-name patches match their exact counts, and the app key (data folder, registry key) is unchanged. |

A failed check before apply writes nothing; a failure after apply puts every
file back.

The tables are written for DEV. A build of a tree whose upstream base is not
DEV (an integration onto an older upstream tag: a pull request into
`cosmyx-ci/<tag>`, or an `integration/<tag>` branch) brands in tolerant mode:
a colour or product-name row whose file or text that tree lacks entirely, and
a replacement of an upstream file it does not have, are skipped with a
warning. A text found with another count still fails. DEV, MIXED and release
builds are strict. `just brand-mode` prints the mode the environment selects;
`just brand-apply tolerant` brands an older tree locally (decision 0122).

Line endings never matter. A Windows checkout (`core.autocrlf`, the default on
the runners) has CRLF text files: every match and count is made on LF text, a
patched file is written back with its own line ending (never a mix), and the
canonical-form checks and SVG hashes compare LF content, so a tree brands and
checks the same on every OS.

## Local use

- `just brand-apply` brands your checkout; `just brand-revert` restores every
  file byte for byte (the backups live in `build/cosmyx/branding-state/`).
  Running `brand-apply` twice is the same as once.
- `just brand-sync`, `brand-refresh` and `brand-validate` refuse a branded
  tree: revert first.
- The last run's report is `build/cosmyx/branding-report.json`.

## Colours

The build turns the Orca teal into the Cosmyx violets. Everything is in
`cosmyx-src/branding/colours.json`; the stage itself is
`scripts/cosmyx/branding/colours.py`.

### How a colour changes

1. **Literal rows** (`literals`) rewrite the colours written as numbers, for
   example `wxColour(0, 150, 136)`, `ImVec4(0.00f, 0.59f, 0.53f, ...)`,
   `0x009688` or `rgba(0, 150, 136, .18)`. Each row names one file, the exact
   text, its replacement and how many times the text occurs. A row that no
   longer matches its count stops the build before anything is written.
2. **Snippets** (`snippets`) insert one line after an exact anchor. There is
   one: in dark mode `BitmapCache.cpp` only recolours quoted fills
   (`fill="#..."`), so the snippet adds the bare key that also reaches the CSS
   form (`fill:#...`) of the SVG icons.
3. **The hex rewrite** changes every `#RRGGBB` (any case; an 8-digit colour
   keeps its alpha) whose colour is the `from` of a mapping, to its `to`, in
   uppercase. It never touches an `href`, a `url(...)` reference, a URL
   fragment (`https://...#009688`), a numeric character reference
   (`&#009688;`) or base64 data, and nothing outside the scopes.
4. **The leftover check** runs on the branded tree. Any teal left in the
   scopes (hex, colour tuple or `0xRRGGBB`), and any mapped colour, fails the
   build unless an `allow_residue` row permits that exact count in that file.

The scopes are the GUI sources (`src/slic3r/`, except
`src/slic3r/GUI/Cosmyx/`), the web pages (`resources/web/` `.css`, `.html`,
`.htm`, `.js`, except the vendored Elegoo page and xterm) and, for literal
rows only, `src/libslic3r/Color.hpp`. Filament colours stay as they are
(the profiles, the colour picker swatches), except the default filament
colour: one literal row turns the `#26A69A` fallback of `PresetBundle.cpp`
into the dark grey `#242323` (decision 0128). The
functional highlights drawn on the 3D scene (gizmos, UV editor, sketch snaps)
stay too: those have `allow_residue` rows with their reason. `#00AE42` (the green the
SVG icons use as a placeholder) and `#1F8EEA` are not teal for the engine;
`#FEFFFF` (near white) is ignored too.

### Mappings

Every mapping is a proposal until you validate it: `source` says whether the
colour is yours (`user`) or derived from yours (`derived`), and `status` is
`to-validate` until you change it to `validated` in `colours.json` yourself.
Development builds warn while a mapping is `to-validate`; release builds fail.
You approved the whole table on 2026-11-19, so every mapping is `validated`;
the same day you chose `#33ABA1` (the hover teal of the one-layer icons)
-> `#A472F5` yourself. A new or changed mapping starts again at `to-validate`.

Contrast is the WCAG 2 ratio of the colour on white (`#FFFFFF`) and on the
dark screen background (`#1C1C1F`). Dark mode is forced, so the dark column is
the one that matters most: 3 is the minimum for large text and UI parts, 4.5
for body text.

| From | To | Role | Source | From on white / dark | To on white / dark |
|------|----|------|--------|----------------------|--------------------|
| `#009688` | `#8000FF` | light base (brand) | user | 3.67 / 4.63 | 6.25 / 2.72 |
| `#00675B` | `#A472F5` | dark base (brand on dark screens) | user | 6.79 / 2.50 | 3.33 / 5.10 |
| `#00897B` | `#8000FF` | pressed | derived | 4.32 / 3.94 | 6.25 / 2.72 |
| `#26A69A` | `#A472F5` | light hover | derived | 3.00 / 5.67 | 3.33 / 5.10 |
| `#33ABA1` | `#A472F5` | light hover (one-layer icons) | user | 2.81 / 6.06 | 3.33 / 5.10 |
| `#008172` | `#8000FF` | dark hover | derived | 4.79 / 3.55 | 6.25 / 2.72 |
| `#BFE1DE` | `#DFBFFF` | light tint 25% (checked item) | derived | 1.40 / 12.18 | 1.61 / 10.55 |
| `#E5F0EE` | `#F2E6FF` | light tint 10% (focused item) | derived | 1.16 / 14.60 | 1.20 / 14.20 |
| `#223C3C` | `#382D43` | dark tint 25% (checked item) | user | 11.80 / 1.44 | 12.93 / 1.32 |
| `#283232` | `#393444` | dark tint 10% (focused item) | derived | 13.19 / 1.29 | 12.01 / 1.42 |
| `#52C7B8` | `#B4B9DD` | accent (hovered checked, SVG green) | user | 2.05 / 8.27 | 1.92 / 8.84 |
| `#4DB6AC` | `#B4B9DD` | accent (images) | user | 2.44 / 6.96 | 1.92 / 8.84 |
| `#009687` | `#8000FF` | brand, off by one (links, chips) | derived | 3.68 / 4.62 | 6.25 / 2.72 |
| `#009789` | `#8000FF` | brand, off by one (About link) | derived | 3.63 / 4.69 | 6.25 / 2.72 |
| `#009C88` | `#8000FF` | text selection background (ImGui) | derived | 3.44 / 4.95 | 6.25 / 2.72 |
| `#00BFBF` | `#8000FF` | text selection background (notifications) | derived | 2.28 / 7.45 | 6.25 / 2.72 |
| `#007A74` | `#8000FF` | sketch banner (CAD panel) | derived | 5.20 / 3.27 | 6.25 / 2.72 |
| `#22BFB0` | `#A472F5` | confirm button focus border, dark | derived | 2.30 / 7.41 | 3.33 / 5.10 |
| `#00FFD4` | `#B4B9DD` | confirm button focus border, light | derived | 1.29 / 13.16 | 1.92 / 8.84 |
| `#244945` | `#382D43` | web dark theme selected row | derived | 9.93 / 1.71 | 12.93 / 1.32 |
| `#5EEAD4` | `#A472F5` | web dark theme link text | derived | 1.48 / 11.49 | 3.33 / 5.10 |
| `#8DE5D6` | `#B4B9DD` | web dark theme own-source text | derived | 1.47 / 11.59 | 1.92 / 8.84 |
| `#00FFEA` | `#A472F5` | homepage link button | derived | 1.27 / 13.35 | 3.33 / 5.10 |
| `#00C8B4` | `#A472F5` | texture projector frame border | derived | 2.12 / 8.03 | 3.33 / 5.10 |

To see the table again, with the blends the derived colours come from and the
contrast of text on each fill, run `just brand-colour-candidates` (it writes
nothing).

Points to look at when you review:

- `#8000FF` on the dark background is 2.72: where a colour maps to `#8000FF`
  and is drawn on dark without going through the dark map (the dark hover,
  the links in HTML dialogs such as About), it is hard to read. Mapping those
  roles to `#A472F5` instead is one edit of the `to` column.
- White text on `#A472F5` is 3.33, enough for buttons (large text) only.
- The dark tint 10 is `#393444`; the exact blend of `#A472F5` at 10% over the
  panel background `#2D2D31` is `#393445`.
- Icons drawn by OpenGL or ImGui (`GLTexture`, the toolbar and gizmo icons)
  keep the colour of their file on disk: they turn violet only when their SVG
  is replaced (the SVG candidates task).

### After an upstream merge

A literal row whose count changed, or a new teal colour, stops the build
(G5). Run `just brand-colour-literals` to regenerate the tuple rows from the
tree (rows written by hand, whose reason does not start with `tuple `, are
kept), review the diff of `colours.json`, and add a mapping or an
`allow_residue` row for a new teal colour.

## Dark mode

Dark mode is forced for everyone, on every system, and cannot be switched
off: there is no way back to the light theme, and the Windows Preferences
toggle has no effect (decision 0139). Replacements therefore only need to
look right on the dark background; the `_dark` variants of the logos are the
ones on screen.
