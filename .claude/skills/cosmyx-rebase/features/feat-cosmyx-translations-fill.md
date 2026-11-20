# feat/cosmyx-translations-fill (PR #108)

## Purpose

The translation graft of PR #95 ships the Cosmyx catalogues, but in that PR only 38 of the 396 non-English entries (18 msgids x 22 languages) carry a translation (seeded from the old branch `cosmyx-2.3.1-7`); the rest is empty and the build falls back to the English text. This branch fills every remaining entry in all 22 OrcaSlicer languages for the three Cosmyx catalogues (CHT nozzle, ironing temperature, Cosmyx models), using each language's own OrcaSlicer vocabulary for shared words (for example "ironing", "nozzle", "calibration"). After it, no Cosmyx entry is empty or fuzzy (checked: 396 entries, 0 empty, 0 fuzzy), so a user running OrcaSlicer in French sees the Cosmyx labels in French.

It adds no code, no hook and no upstream file; it is pure data plus a changelog line. One commit per language, each produced by a translator working in that language only, per the project rule that translation changes go to one agent per language.

## Parent and dependencies

- Parent: `feat/cosmyx-translations` (PR #95), itself on `DEV`; depends on #86 and #95 (their commits show in the diff until they merge).
- Depends on the graft rules in `scripts/cosmyx/i18n_graft.py` (translated, non-fuzzy Cosmyx entry replaces an Orca one), on the Cosmyx catalogue layout `localization/cosmyx/<feature>/<lang>.po`, and on the Orca catalogues `localization/i18n/<lang>/OrcaSlicer_<lang>.po` for the shared terms and for `Language` / `Plural-Forms` headers.
- No upstream files, strings or APIs are touched.

## Changes

| File | Kind | What it does |
|---|---|---|
| `localization/cosmyx/cht-nozzle/<lang>.po` (only the languages whose entry was still empty, 7 files; `en.po` untouched) | data | Fills the `CHT` entry. `CHT` is an acronym that stays in English in most languages; seeded values are kept as they were (decision 0085). |
| `localization/cosmyx/ironing-temperature/<lang>.po` (22 files) | data | Fills `Ironing temperature` and the description "Nozzle temperature while this filament irons. The nozzle goes back to the print temperature once ironing is done. 0 means no change." |
| `localization/cosmyx/models/<lang>.po` (all 22 languages) | data | Fills the 15 calibration-model menu entries (`Calibration Suggestion`, `Cosmyx 3D Models`, `Calibration Models Dual Head`, ...). Proper names such as `Cosmyx Cube` or the French model names (`Cube Bicolore`, `Support Bobine`, `Calage 1 SNDT`) may stay as they are. |
| `CHANGELOG.md` | docs | One line under `<!-- cosmyx-slot: T8 -->`, above the translations line: "Fill the Cosmyx catalogues in all 22 OrcaSlicer languages ...". |

Schema (unchanged from #95): standard gettext PO keyed by (msgctxt, msgid); `msgid` values are the English source strings extracted from `src/**/Cosmyx/**` and must never be edited here; only `msgstr` is filled; headers keep `Language` and `Plural-Forms` copied from the Orca catalogue; no `# AI Translated` handling is applied by the graft. 52 files, 22 language commits (`ecf391e19e` Catalan ... `323af0b256` Traditional Chinese) plus the changelog commit `e36feb81c8`.

## Rebase risk zones

- Low. The branch edits only Cosmyx-owned data files. Against `upstream/v2.5.1` the graft dry-run of the filled catalogues on a v2.5.1 tree appends 18 entries per language with 0 replaced and 0 errors; none of the 18 msgids exists in the v2.5.1 `OrcaSlicer.pot` (so no silent override of an Orca translation).
- The language set of `localization/i18n` is identical in v2.5.1 and DEV (22 languages plus `en`), so no catalogue is missing.
- Real risk is on the parent: if `feat/cosmyx-translations` changes a template (`messages.pot`) or `i18n_extract` rewrites `<lang>.po` after a Cosmyx source string changed, entries here conflict or become stale. A msgid whose English text changed after the fill is a new msgid for gettext and comes back empty.
- If upstream later adds one of the 18 msgids, decision 0084 removes it from the template on the next extraction and the upstream translation takes over; the filled value would then be dropped, which is intended.

## Intent to preserve

- Every entry of the three catalogues is translated in all 22 languages, none fuzzy (fuzzy entries are hidden from users and never win in the graft).
- Shared words match the OrcaSlicer catalogue of the same language (use the glossary and the existing Orca terms, not new wording); acronyms (`CHT`), product and model names stay as they are.
- Never change a `msgid`. If a source string is wrong, fix it in the Cosmyx source and re-run `just i18n-extract`, then translate the new msgid; do not fix wrong English in a translation.
- Plural forms follow the `Plural-Forms` header of each catalogue (none of the current msgids is plural).
- During a rebase do not retranslate or reflow entries; resolve conflicts by keeping the translated side, and send any new or changed msgid to a fresh per-language translator agent (one agent per language).
- No branding status or validation applies.

## Verification

- `just i18n-graft-dry-run` (all languages graft with no error, counts `0 replaced, 18 appended` on a base without Cosmyx strings).
- `just test-scripts`, or `PYTHONDONTWRITEBYTECODE=1 COSMYX_TEST_PROFILE=prepare python3 -m unittest discover -s scripts/cosmyx/tests -p test_i18n_graft.py -t scripts/cosmyx/tests` (it checks every feature has every language and the same msgids as its template).
- Per catalogue, on a machine with gettext (Debian container works: `docker run --rm -v "$PWD:/repo" -w /repo python:3.12-slim-bookworm sh -c "apt-get update -qq && apt-get install -y -qq gettext >/dev/null && for f in localization/cosmyx/*/*.po; do msgfmt --check-format --check-header -o /dev/null \$f || exit 1; done"`). The PR recorded `msgfmt --check-format` passing on all 66 catalogues.
- Emptiness check: no `msgstr ""` for a non-header entry in any `localization/cosmyx/*/<lang>.po` except `en.po` (English source).
- `git diff origin/<parent>..HEAD --stat` must show only `localization/cosmyx/**` and `CHANGELOG.md`.

## Known pitfalls

- The PR body lists commit hashes of an earlier push (for example `caf0b0a1d7` Catalan); the branch was rewritten on top of the updated parent, so use `git log origin/feat/cosmyx-translations..origin/feat/cosmyx-translations-fill` for the real shas (`ecf391e19e` Catalan, `ca455413da` German, `59da003c14` French, `323af0b256` Traditional Chinese, `e36feb81c8` changelog).
- Seeded values from the old branch were kept as they were, including `CHT` translated as `CHT`; do not "improve" them.
- Cosmyx catalogues must stay UTF-8 (decision 0088), LF line endings in git; a catalogue saved in another encoding fails the graft with a named error.
- Fuzzy flags: an entry left fuzzy is skipped by msgfmt and never wins the graft; clear the flag when correcting (the same rule as upstream).
- No file may carry the `OrcaSlicer` prefix and none may sit under `localization/i18n` (upstream tooling globs them).

## Shared files with other branches

- `CHANGELOG.md`: adds a line directly under `<!-- cosmyx-slot: T8 -->`, the same slot as `feat/cosmyx-translations`; on a rebase keep both lines, this one first, and leave the slot marker where it is.
- `localization/cosmyx/cht-nozzle/`, `ironing-temperature/`, `models/`: also written by `just i18n-extract` on the feature branches that own those strings (cht-nozzle, ironing-temperature, models). Those branches add or reword msgids; the fill must be redone for any new msgid.
- Nothing in `justfile`, `scripts/cosmyx/` or `wiki/decisions/` is touched, so no overlap there.
