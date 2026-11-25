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

## Dark mode

Dark mode is forced for everyone, on every system, and cannot be switched
off: there is no way back to the light theme, and the Windows Preferences
toggle has no effect (decision 0139). Replacements therefore only need to
look right on the dark background; the `_dark` variants of the logos are the
ones on screen.
