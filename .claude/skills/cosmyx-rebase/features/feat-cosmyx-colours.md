# feat/cosmyx-colours (PR #102)

## Purpose

Turns the Orca teal into the Cosmyx violets in the built app, without editing any upstream file in git. At build time the colour stage of the branding engine rewrites colours in the GUI sources (`src/slic3r/`) and the web dialogs (`resources/web/`), so buttons, links, selections, hovers, tints and dark-theme accents are violet instead of teal. The user's four colours are `#8000FF` (brand), `#A472F5` (brand on the dark screen `#1C1C1F`), `#382D43` (dark) and `#B4B9DD` (lavender); the other roles (hover, pressed, tints, off-by-one shades) are derived from them.

What it contains:

- 24 colour mappings (`from` Orca teal to `to` palette violet, with a role, a source `user` or `derived` and a status). All are `validated`: the user approved the whole table on 2026-11-19 in their own words, and chose the 24th mapping (`#33ABA1` -> `#A472F5`, the one-layer icon hover) themselves.
- 115 exact literal rows for colours written as numbers (`wxColour(0, 150, 136)`, `ImVec4(0.00f, 0.59f, 0.53f, ...)`, `0x009688`, `rgba(0, 150, 136, .18)`, an ABGR integer `0xFF889600` in `BitmapCache.cpp`), in 69 files.
- One snippet: in dark mode `BitmapCache.cpp` only recolours quoted fills, so one line is inserted to also reach the CSS-form SVG fills.
- A guard (G5) that fails the build on any teal left in the colour scopes unless an `allow_residue` row permits that exact count with a reason (colour-picker swatches, filament default colours, 3D highlights, test data).
- WCAG contrast of every mapping on white and on the dark screen is reported (informs review, never fails a build). Recipes `just brand-colour-candidates` and `just brand-colour-literals`.

Decisions: 0127 (mappings), 0128 (explicit rewrite), 0129 (residue), 0130 (limits), and an edit of 0123 (hex rule). Changelog slot T11c.

## Parent and dependencies

- Parent: `ci/cosmyx-branding-engine` (PR #99); needs #95 and #86 below it. PR #102 targets `DEV`.
- Uses the engine's apply pipeline (literal rows applied with `textpatch` before the plugin, plugin interface `apply(ctx, backup)` / `guards(ctx, phase)`), guards G5 and G7, `COLOURS_FILE`, `hex_is_skipped`, the status policy and report.
- Interacts with the logos branch (#101, sibling: both child of the engine) only through the shared files below; it does not depend on it.
- Depends on `dark mode is forced` (decision 0139, another branch): the dark-screen contrast column is the one that matters, and `BitmapCache.cpp`'s dark replace map drives the snippet.
- Upstream files read and edited at build time (not in git): the 69 files named by literal rows (for example `src/slic3r/GUI/BitmapCache.cpp`, `Widgets/TempInput.cpp`, `Widgets/TextInput.cpp`, `resources/web/dialog/css/theme.css`, `PluginsDialog/styles.css`, `SpeedDial/style.css`) and every file matching the scopes.
- Not covered by this branch: icon SVGs loaded by OpenGL/ImGui (`GLTexture`, `ImGuiWrapper`, `IconManager`) keep their file colour until the SVG-candidates branch replaces them (decision 0130).

## Changes

| File | Kind | What it does |
|---|---|---|
| `cosmyx-src/branding/colours.json` | data | The colour table, schema 1, keys: `palette`, `mappings`, `family`, `ignore`, `scopes`, `literals`, `snippets`, `allow_residue`. See below for each. |
| `scripts/cosmyx/branding/colours.py` | Cosmyx-owned plugin | `apply(ctx, backup)`: applies `snippets`, then the hex rewrite over the scopes; `guards(ctx, phase)`: G5 leftover scan (hex, colour tuples, `0xRRGGBB`, mapped colours outside the family) against `allow_residue`; WCAG contrast and blends; CLI `candidates` and `literals [--write]`. |
| `scripts/cosmyx/branding/__init__.py` | Cosmyx-owned (edited) | Adds `hex_is_skipped(before)` and `HEX_LOOKBACK = 2048`: a `#` is not a colour inside an `href`/`url(...)`, a URL fragment (`scheme://...#RRGGBB`), a numeric character reference (`&#NNNNNN;`) or base64 data. Shared by the scan and the rewrite. |
| `scripts/cosmyx/just/branding-colours.just` | Cosmyx-owned | `brand-colour-candidates` (print mapping table with contrast, writes nothing), `brand-colour-literals` (regenerate tuple rows from the tree). |
| `scripts/cosmyx/tests/test_branding_colours.py`, `test_breaker_branding_colours.py` | test | Hex rule (case, 8-digit alpha, href/url/base64 untouched), tuple recogniser and notation-preserving rewrite, WCAG maths, table validation, snippet anchors, stale literal rows, new teal caught, status policy, CLI, committed table (rows current, wiki table current, mappings `validated`, release build accepts it), a real-tree apply on a scratch copy that leaves no teal and reverts exactly. |
| `wiki/cosmyx/branding.md` | docs (edited) | `## Colours` section: how a colour changes, scopes, the 24-row mapping table with contrast, what to do after an upstream merge. |
| `wiki/decisions/0127-0130*.md`, `wiki/decisions/0123-branding-manifest.md` | docs | Four decisions; 0123 gains the URL-fragment and character-reference exclusions. |
| `CHANGELOG.md` | docs | One line under slot T11c. |

Schema of `colours.json` and how rows anchor to upstream text:

- `palette`: seven named colours (`brand #8000FF`, `brand_dark_screen #A472F5`, `dark #382D43`, `lavender #B4B9DD`, `tint25 #DFBFFF`, `tint10 #F2E6FF`, `dark_tint10 #393444`), all uppercase `#RRGGBB` (guard G7 greps each as a case-insensitive substring of tracked files, so short or non-colour values are rejected).
- `mappings`: `{from, to, role, source: user|derived, status: to-validate|validated}`. `from` is an Orca teal hex, unique and not ignored; `to` must be a palette colour. The hex rewrite changes every `#RRGGBB` (any case, 8-digit keeps alpha, output uppercase) equal to a `from`, only inside the scopes. Anchor: the colour itself, no surrounding text.
- `family` (`hue [160,190]`, `min_saturation 0.25`, `min_lightness 0.15`) and `ignore` (`#00AE42`, `#1F8EEA`, `#FEFFFF`): the teal-family recogniser, which never rewrites and only finds leftovers.
- `scopes`: fnmatch globs on repository paths, `!` excludes: `src/slic3r/*.{cpp,hpp,h,mm}` except `src/slic3r/GUI/Cosmyx/*`; `resources/web/*.{css,html,htm,js}` except `resources/web/elegoolink/*` and `resources/web/include/xterm/*`; `src/libslic3r/Color.hpp` (literal rows only). `PresetBundle.cpp`, profiles and colour-picker swatches stay out.
- `literals`: `{file, find, replace, count, reason}`: exact text in one file with an exact occurrence count (matched on LF text). Anchor: the literal text in that file. 114 rows have a reason starting `tuple ` (generated by `just brand-colour-literals`, notation preserved: `rgba(0, 150, 136`, `ImVec4(0.00f, 0.59f, 0.53f`, `0x009688`, `150.f / 255.f`...) and 1 is hand-written (`BitmapCache.cpp`: `0xFF889600` -> `0xFFFF0080`, ABGR). Hand-written rows are kept when regenerating.
- `snippets`: `{file, anchor, insert, count, reason}`: one line inserted after an exact anchor. The only row: file `src/slic3r/GUI/BitmapCache.cpp`, anchor `        replaces["#262E30"] = "#EFEFF0"; // ORCA`, insert `        replaces["#8000FF"] = "#A472F5"; // Cosmyx: CSS-form brand violet on dark`, count 1 (relies on `std::map` ordering: quoted keys apply first).
- `allow_residue`: `{file, match, count, reason}` where `match` is `#RRGGBB`, `rgb(R, G, B)` or `0xRRGGBB`: 41 rows in 18 files (colour picker palettes and test, filament swatches, `ColorRGB(A)::CYAN()`, 3D canvas, UV editor and gizmo highlights, CAD sketch tool, an unused test stylesheet), plus two rows permitting the `#8000FF` that upstream already has (`resources/web/dialog/ColorPickerDialog/palettes.js`, `tests/fff_print/test_helpers.cpp`) for guard G7.

## Rebase risk zones

Checked against `upstream/v2.5.1` by laying this branch's engine and tables over the extracted tag tree and running `cli.py check`/`apply`, plus a script that recounts every row.

- **Missing file (blocking on v2.5.1 as-is).** One literal row targets `src/slic3r/GUI/Gizmos/GLGizmoPaintedModifier.cpp` (`ImVec4(0.f, .59f, .53f` x3), a file that exists in DEV but not in v2.5.1. `check` and `apply` then end with `error: G5 ... cannot read: [Errno 2] No such file or directory` and the build is refused. Regenerate with `just brand-colour-literals` (it recomputes the 114 tuple rows from the tree; on v2.5.1 it returns 114 rows, i.e. the 115 minus this one) and review the diff of `colours.json`. After removing that row, `apply` on the v2.5.1 tree edits 123 files with 0 errors and `revert` restores them exactly.
- Counts: of the 115 literal rows, 114 match their exact counts on v2.5.1 and 115/115 on current DEV. 14 of the 69 literal files changed between the merge-base (65aab6bcf7) and v2.5.1 (`PluginsDialog/styles.css`, `SpeedDial/style.css`, `DesignPanel.cpp`, `CameraPopup.cpp`, `GCodeViewer.cpp`, `GLCanvas3D.cpp`, `GLGizmoMeasure.cpp`, `MainFrame.cpp`, `ReleaseNote.cpp`, `SelectMachine.cpp`, `SendToPrinter.cpp`, `StatusPanel.cpp`, `MultiNozzleSync.cpp`, `SwitchButton.cpp`) but the counts survived. Any change adding or removing a teal tuple in one of them breaks an exact count (a G5 error that stops the build before anything is written, on every build kind).
- Snippet anchor: the `BitmapCache.cpp` line `replaces["#262E30"] = "#EFEFF0"; // ORCA` occurs once on both v2.5.1 and DEV (BitmapCache.cpp had 1 commit in six months, none between merge-base and the tag). If upstream reworks the dark replace map, the snippet fails with a missing/ambiguous anchor and must be re-anchored on the new equivalent line; then check that the CSS-form SVG fills still turn violet in dark mode.
- `allow_residue`: the 41 rows apply cleanly on v2.5.1 (the check and apply of the engine passed with the missing row removed). They are exact counts of colours in files that upstream edits (gizmos, UV editor, CAD sketch tool, `Color.hpp`); a change of count in any of them, or a new cyan/teal highlight, raises a G5 residue error that needs either a mapping or a new allow row with a reason.
- Churn of the scopes: `src/slic3r/` is changed constantly, and `resources/web` had 114 DEV commits in six months (6 tag-side commits since the merge-base). A new teal colour in either goes unnoticed in git but fails G5 at build time; this is the main recurring maintenance. The mapping/`family` recogniser (hue 160-190) catches shades not yet mapped.
- No new teal SVG icons appeared in v2.5.1 (G4 clean); the 3 painted-modifier icon rows of the manifest are DEV-only (see the engine file).
- Hex-rule edge cases: URL fragments (`https://...#009688`) and `&#NNNNNN;` references are skipped; a new upstream pattern that looks like a colour but is not (for example a different encoding of an anchor) needs the shared `hex_is_skipped` updated, not a per-file exception.
- Upstream already contains `#8000FF` in two files (G7 allow rows). A newly added upstream `#8000FF`, or any of the other palette values (`#A472F5`, `#382D43`, `#B4B9DD`, `#DFBFFF`, `#F2E6FF`, `#393444`) in tracked upstream-owned files, fails G7 until an `allow_residue` row is added.

## Intent to preserve

- After branding, no upstream teal remains in the colour scopes except the allow-listed, deliberately untouched colours: filament colours, colour-picker swatches, functional highlights in the 3D scene and UV editor, test data. A new teal anywhere in the scopes must fail the build until someone decides on it.
- Every changed byte is traceable to one mapping or one row; counts are exact; nothing is rewritten by guessing (no "any teal-looking colour becomes violet"). Filament colours stay as they are.
- The mapping `to` values come from the user's palette; roles on dark screens use `#A472F5`, light-base roles `#8000FF`. Do not change a `from`/`to` pair, a palette colour or a `role` while rebasing.
- Statuses: all 24 mappings are `validated` (user approval of 2026-11-19, decision 0127). A rebase must not change any `status`. **An agent must never flip a status to `validated` in `colours.json`, never run `just brand-validate`, and must add any new or changed mapping as `to-validate`, to be approved by the user.** Note that the `brand-validate` command covers manifest rows only; the colour table is edited directly by the user, and a release build fails on any non-validated mapping.
- If upstream rewrote colour code (a new tuple notation, a renamed variable, a moved dark map), re-anchor: regenerate tuple rows with `just brand-colour-literals`, add an `allow_residue` row (with an honest reason) only for colours that are not branding, add a mapping (proposed to the user as `to-validate`) for a new brand colour, and re-anchor the snippet on the new equivalent line. Do not force the old literal text or old counts onto changed code.
- The wiki mapping table and contrast figures must match the committed table (a test pins this).

## Verification

From the repository root, after the rebase:

- `just brand-colour-literals`, then `git diff cosmyx-src/branding/colours.json`: only rows tied to files or counts that really changed upstream may differ. (The recipe writes `colours.json` in place; review, do not blindly accept.)
- `just brand-check` (0 errors) and `just brand-apply` then `just brand-revert` with an empty `git status --short` afterwards; the apply report lists the colour stage and counts; no G5 residue error.
- `just brand-colour-candidates` and compare with the `## Colours` table in `wiki/cosmyx/branding.md` (mappings and contrast unchanged).
- `PYTHONDONTWRITEBYTECODE=1 COSMYX_TEST_PROFILE=prepare python3 -m unittest discover -s scripts/cosmyx/tests -p 'test_branding_*.py' -t scripts/cosmyx/tests` (includes `test_branding_colours.py`: real-tree apply leaves no teal, reverts exactly, mappings validated); `python3 scripts/cosmyx/run_script_tests.py` / `just test-scripts` for the full run, including `test_breaker_branding_colours.py`.
- Release acceptance: `COSMYX_BRAND_REF=refs/tags/v0 python3 scripts/cosmyx/branding/cli.py check` still reports the colour table as acceptable (image rows may still warn or fail by policy).
- `just decisions`.

## Known pitfalls

- `836054eaf8` (tests `aa0304b439`) a URL such as `https://example.org/page#009688` was recoloured and broken, and the HTML character reference `&#129688;` (an emoji) read as teal and was reported as residue. A `#` inside a `scheme://` run or right after `&` is no longer a colour; palette values are validated as uppercase `#RRGGBB` because G7 greps them as substrings.
- `c9a1d85718` Windows CRLF checkouts: the colour stage read scopes as raw text, so a tuple spanning a line break matched differently than in `colours.json`; scopes are now read as LF text and the committed-table test compares ignoring line endings.
- `d7f6e9f451` all mappings were marked `validated` by direct edit of the table after the user's approval (the validate command covers manifest rows only); tests pin the committed table as validated and check that a release build accepts it. `f8ca0311ea` the user added the 24th mapping `#33ABA1` -> `#A472F5` (source `user`).
- The PR body says 23 mappings and all `to-validate`; the branch now has 24, all `validated`.
- Tuple rows keep each file's notation; regenerating with `just brand-colour-literals` keeps hand-written rows (reason not starting with `tuple `) so do not give a hand-written row a reason starting with `tuple `.
- The engine's `copy_real_tree` test helper copies the colour scopes and rows whenever `colours.json` exists; do not replace it with a per-stage copy (it caused conflicts with the product-name branch).
- Icons drawn by OpenGL/ImGui stay teal until their SVG is replaced; this is expected (decision 0130), not a bug of the colour stage.
- v2.5.1 pass: adapted with `2b46a70b77`; `just brand-colour-literals` removed exactly the `GLGizmoPaintedModifier.cpp` row (114 rows), mappings and statuses unchanged, `brand-check` 0 errors.
- v2.5.2 pass: same G5 error on `GLGizmoPaintedModifier.cpp`; `just brand-colour-literals` removed the same row (114 rows), committed as `33fbc1c012`.

## Shared files with other branches

- `wiki/cosmyx/branding.md`: this branch adds `## Colours`; logos adds `## Logos`; product name, candidates and dark default add their own. Keep all sections on conflict.
- `wiki/decisions/0123-branding-manifest.md`: edited here (hex rule) though owned by the engine branch.
- `scripts/cosmyx/branding/__init__.py`: edited here (`hex_is_skipped`); engine owns the file, the product-name branch may add to it.
- `scripts/cosmyx/branding/guards.py` and the real-tree test setup (`branding_fixture.py`, `copy_real_tree`): G5 and G7 read `colours.json`; sibling branches use the same fixture.
- `CHANGELOG.md`: slot T11c only (area `GUI`).
- `wiki/decisions/`: 0127-0130 are this branch's numbers (engine 0120-0123, logos 0124-0126; dark mode 0139).
- `cosmyx-src/branding/colours.json`: also read by the SVG-candidates branch (candidate icons use the palette) and G7 uses its palette for every branch; any other branch needing a colour exception adds an `allow_residue` row here, a conflict hot spot for sorted-table edits.
- `scripts/cosmyx/just/branding-colours.just`: own file, loaded by `import?` in `branding.just`.
- Overlay and manifest: none touched; logos (#101) and colours (#102) are independent siblings under the engine and merge in any order.
