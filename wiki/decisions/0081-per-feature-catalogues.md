# 0081. One translation catalogue per feature

## Status

Accepted.

## Context

Features are developed on parallel branches. A single Cosmyx catalogue per
language would make every feature branch edit the same files. The Windows
script `scripts/run_gettext.bat` compiles every `*.po` found under
`localization/i18n`, and the CMake gettext targets glob `OrcaSlicer*.po`, so a
Cosmyx file there, or one named with the OrcaSlicer prefix, would be picked up
by upstream tooling.

## Decision

- Layout: `localization/cosmyx/<feature>/messages.pot` (the template) and
  `localization/cosmyx/<feature>/<lang>.po`, one per language folder of
  `localization/i18n`, all present even when untranslated. Each `<lang>.po`
  header copies `Language` and `Plural-Forms` from the OrcaSlicer catalogue of
  that language. No file carries the OrcaSlicer prefix.
- Every source file below a `Cosmyx` folder of `src/` is extracted. Its feature
  is decided in one place, `feature_for()` in `scripts/cosmyx/i18n_extract.py`:
  an explicit `STEM_FEATURES` entry (`CosmyxAbout` -> `version`), else the
  kebab-case file stem without a leading `cosmyx-`, folded into the shortest
  known feature that is a word prefix of it (`CosmyxModelsMenu` -> `models`).
- A feature with no strings has no folder (bed-temperature-off and
  stealth-mode have none today).

## Consequences

- Each feature branch adds or changes only its own folder.
- Translators work on one small file per feature and language.
- The graft test checks that every feature has every language and the same
  msgids as its template.
- Removing it: merge the folders into one catalogue per language, or drop them
  with decision 0080.
