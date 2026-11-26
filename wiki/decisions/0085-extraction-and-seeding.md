# 0085. Extraction with xgettext, seeding from the old branch

## Status

Accepted.

## Context

The Cosmyx sources are not listed in `localization/i18n/list.txt` (an upstream
file), so the upstream extraction never sees them. GNU xgettext is not
installed on every development machine. The previous Cosmyx branch
(`cosmyx-2.3.1-7`) kept a few translations inside the OrcaSlicer catalogues.

## Decision

- `just i18n-extract` runs xgettext over `src/**/Cosmyx/**` with the same
  keywords and options as the upstream `gettext_make_pot` target (`L`, `_L`,
  `_u8L`, `L_CONTEXT:1,2c`, `_L_CONTEXT:1,2c`, `_u8L_CONTEXT:1,2c`,
  `_L_PLURAL:1,2`, `TRN` comments, `--boost`), then refreshes every
  `<lang>.po`: new msgids untranslated, removed ones dropped, translations and
  translator comments kept. A template whose only change is its creation date
  is not rewritten. Without xgettext the recipe stops and says how to install
  it, or to use `just i18n-extract-docker`, which runs the same script in a
  Debian Python image with gettext.
- `just i18n-seed REF` fills empty Cosmyx entries from the OrcaSlicer
  catalogues of a git ref, for exact (msgctxt, msgid) matches with a
  translated, non-fuzzy entry only. The first templates were seeded from
  `cosmyx-2.3.1-7`; strings whose English changed since were left empty.
- Seeded values are kept as they were, including `CHT` translated as `CHT`, an
  acronym that stays in English.
- **Catalogues stay in sync with the sources.** A script test runs the
  extraction on a copy of `localization/cosmyx` and fails when any file would
  change, so a string added, reworded or removed without `just i18n-extract`
  is caught. A template's header is left out of the comparison, since it is
  xgettext's and changes with its version. The test needs GNU xgettext: the
  Linux leg of `cosmyx-checks` installs it and sets
  `COSMYX_REQUIRE_GETTEXT=1`, which turns a missing xgettext into a failure;
  elsewhere the test skips and says why.
- **Coverage is reported, and enforced on request.** `just i18n-coverage`
  lists, per feature and language, every entry a user would see in English:
  empty (or a plural with an empty form), fuzzy, or equal to its msgid.
  English catalogues are skipped. `scripts/cosmyx/i18n_coverage_allow.json`
  lists the msgids that may stay as their source (acronyms such as `CHT`,
  proper names), for every language or per language. The repository test of
  that report only fails with `COSMYX_I18N_STRICT=1`: feature branches
  translate French only and a per-language pass fills the other languages
  later, so an always-on check would fail every feature branch until that
  pass lands. Once it has, setting the variable in `cosmyx-checks` makes
  coverage a gate.

## Consequences

- One command refreshes every catalogue after a source change.
- Translations of reworded strings are not carried over; the language agents
  translate them.
- Removing it: delete the script and its recipes; the catalogues then have to
  be edited by hand.
