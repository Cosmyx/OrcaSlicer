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
| `cosmyx-src/branding/product-name/` | The product name: `patches.json`, `rename.json`, `allowlist.json`, `inflections.json` (see [Product name](#product-name)). |
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
  icon, the macOS app icon and the four MSIX tiles. Never edit one by hand. To change them,
  change the master or the list, then:

  ```text
  just brand-derive              # re-render, rewrite only what changed
  just brand-refresh <path>      # for each rewritten file: back to to-validate
  ```

  `just brand-derive-check` fails when a committed output differs from a
  fresh render, `just brand-derive-stable` renders twice and compares. They
  render in the pinned resvg image (`scripts/cosmyx/branding/derive/Dockerfile`),
  so they need Docker with Linux containers.

The overlay covers the application icon (window, taskbar, dock, executable,
installer, Linux desktop and MSIX icons), the About dialog logos and the splash
screen. The other `logos` rows stay `missing`, so the build keeps the Orca
files for them.

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
| G8 | Product-name patches and rename rows match, literals and msgids are renamed together, no visible upstream name is left outside the allowlist, the app key (data folder, registry key) is unchanged, every packaging pin (AppImage intermediate file names, Linux binary name, CPack package name, Flatpak id) is identical after apply, and the AppImage launcher name matches the file its script moves. |

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

## Product name

The build shows the name CosmoSlice, including the installer's Apps &
features name, the Start menu and desktop shortcut label and the Flatpak
software centre name and description (decision 0132). The app key stays
OrcaSlicer, so the data folder, `OrcaSlicer.conf`, the bundle id, the Linux
binary `orca-slicer` and the Flatpak id do not change. The Windows install folder, registry
key and installer window title belong to the installer identity
(`cmake/cosmyx/Packaging.cmake`, decision 0182).

Four tables in `cosmyx-src/branding/product-name/`:

| Table | Rows | What it does |
|-------|------|--------------|
| `patches.json` | `{file, old, new, count, reason}` | Exact text patches, applied first: `SLIC3R_APP_NAME`, the display-name macros, packaging names, window titles, and the machine-read sites rewired to `SLIC3R_APP_KEY` (decision 0133). |
| `rename.json` | `{kind, old, new, source}` | Whole texts: a `msgid` row renames the C++ literal (or hint) and the msgid in the template and every catalogue together, translations included, never fuzzy; a `literal` row renames a visible text without a msgid (decision 0134). |
| `allowlist.json` | `msgid`, `literal` or `text` rows with a `reason` | Texts that keep the upstream name on purpose: credits, upstream releases, CLI output, compared or persisted tags, ids sent to other services, icon names (decision 0135). |
| `inflections.json` | `{language, old, new, source}` | Per catalogue language, an inflected name (cs "OrcaSliceru", hu "OrcaSlicerrel", eu "OrcaSlicerren") or a phrase around the inflected, plain or hyphenated name (hu "az OrcaSlicer" -> "a CosmoSlice", eu "Orca-ren" -> "CosmoSlice-en"), and its CosmoSlice form, written by a speaker of that language, never guessed; a row whose `old` names the cloud (hu "az OrcaCloud" -> "a Cosmyx Cloud") renames the words around Cosmyx Cloud; sorted by language, then `old` (decision 0134). |

The upstream cloud service becomes Cosmyx Cloud (Orca Cloud, OrcaCloud), a
brand name kept in English in every language; a suffix glued to it in a
translation stays, and a word before it that changes with it (ca/fr "d'",
hu "az") needs an inflection row (decision 0134).

Names that name an upstream thing are never rewritten: Orca Cube,
Orca String Hell, Orca Tolerance Test, Orca YOLO, Orca Arena, Orca Palette,
Orca Badge, OrcaSliced Combo, Orca Preset Bundle, Orca Filament Library, and
any name inside a URL, file or path name, or dotted id. Names tied to the app
key stay too, because they point at real files: `OrcaSlicer.conf` and the
Windows data folder (`%APPDATA%\OrcaSlicer`). `OrcaSlicer.app` and
`OrcaSlicer.AppImage` become `CosmoSlice.app` and `CosmoSlice.AppImage`, the
packages' own names. "ORCA SLICER" and "ORCASLICER" become "CosmoSlice".

### Package names

Every package a user downloads or runs is named CosmoSlice (decision 0210):

| Package | Name |
|---------|------|
| Windows executable (portable, installer, MSIX) | `CosmoSlice.exe`; MSIX command alias `cosmoslice.exe` |
| Windows installer | `CosmoSlice_Windows_Installer_V<version>_<arch>.exe` |
| Windows artifacts | `CosmoSlice_Windows_<ver><arch>_portable`, `CosmoSlice_Windows_<ver><arch>`, `CosmoSlice_Windows_MSIX_<ver><arch>` |
| macOS | `CosmoSlice.app` in `CosmoSlice_Mac_universal_<ver>.dmg` (volume CosmoSlice), artifact `CosmoSlice_Mac_universal_<ver>`; on a pull request, `CosmoSlice_Mac_<arch>_<ver>` per arch |
| Linux AppImage | launcher name CosmoSlice, file `CosmoSlice_Linux_AppImage<ubuntu><arch>_<ver>.AppImage`, artifact `CosmoSlice_Linux_ubuntu_<ubuntu><arch>_<ver>` |
| Flatpak | `CosmoSlice-Linux-flatpak_<ver>_<arch>.flatpak` (file and artifact) |

`<ver>` is the workflow's `env.ver`; `<arch>` is its arch suffix (Windows
`_x64`, `_arm64`, plus `_msvc` on a cl build; Linux empty or `_aarch64`).

What the build names (the executable, the installer, the AppImage launcher
and the file appimagetool makes from it) is patched before the build by
`patches.json`. What only the workflow names is renamed by the action
`.github/actions/cosmyx-package-names` (`scripts/cosmyx/package_names.py`,
names in `packages.json`), from five `# Cosmyx` hook steps: `mac-app` (before
the Cosmyx macOS signing, which then signs `CosmoSlice.app` and rebuilds its
DMG), `mac-upload`, `windows`, `linux` and `flatpak` (in
`build_flatpak.yml`). Each stage uploads the CosmoSlice packages and deletes
the upstream `OrcaSlicer_` artifacts it replaces. The profile validator is not
exported (decision 0211).

The MSIX identity comes from repository variables, set by a repository admin
(decision 0212): `ORCA_MSIX_IDENTITY_NAME` = `Cosmyx.CosmoSlice`,
`ORCA_MSIX_PUBLISHER_DISPLAY_NAME` = `Cosmyx`, and `ORCA_MSIX_PUBLISHER` =
the signing certificate's subject once that certificate exists (unset until
then: the upstream default applies).

After an upstream merge, `just brand-check` (or the next build) reports:

- a **stale** row (its text is gone upstream): an error; drop or update the row;
- **residue** (a new text naming OrcaSlicer): a warning on development
  builds, an error on release builds. Run `just brand-name-candidates`: it
  prints proposed rename rows and the other literals; add each one to
  `rename.json`, `patches.json`, or `allowlist.json` with its reason.

Translations of renamed strings get CosmoSlice in place of the name,
including the native spellings in Chinese and Korean; nothing else in the
translations changes. An inflected name (the name with a grammatical suffix
glued to it) is renamed only by its `inflections.json` row; a row may also
be a phrase around the name when a word next to it changes with the new name
(the Hungarian article az becomes a; a Basque suffix follows the new name's
sound). Rows match whole words, in their language only, longest first, before
the plain rule. Without a row an inflected name stays, and G8 reports "needs inflection row" (a warning on development
builds, an error on release builds). `just brand-name-inflections` lists every
form still without a row, per language, with an example msgid and
translation (`just brand-name-inflections OUT=<file>` writes it to a file);
hand each language to a speaker of it.

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
