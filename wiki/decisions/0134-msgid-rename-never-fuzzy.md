# 0134. Literals and msgids are renamed together, never fuzzy

## Status

Accepted. Replaces CosmoSlice D-004's fuzzy marking for this fork. Amended:
the token rule (all capitals, combining marks, names tied to the app key)
and the inflection table.

## Context

A translatable text names the product in its C++ literal and in its msgid in
the template and in every catalogue. Renaming one without the other breaks
the translation lookup. CosmoSlice renamed msgids in committed catalogues and
marked the translated entries fuzzy, which hid 76 translations until
translators came back. Here the rename happens at build time, on the
catalogues the T8 graft has already merged.

## Decision

- `rename.json` rows are `{"kind", "old", "new", "source"}`. A `msgid` row
  renames every C++ literal group (adjacent literals joined, decoded) and
  every hint whose value is `old`, and the same msgid (or msgid_plural) in
  `localization/i18n/OrcaSlicer.pot` and every `<lang>/*.po`. A `literal` row
  renames a visible text that has no msgid.
- In a `.po`, the product name in the translation becomes CosmoSlice, with the
  native spellings (zh_CN and zh_TW 逆戟鲸/逆戟鯨, ko 오르카 and
  오르카 슬라이서). Entries are never marked fuzzy and existing flags stay,
  so every renamed string keeps showing its translation. Catalogues are read
  with the T8 parser; untouched entries keep their bytes.
- The name is replaced outside URLs, file and path names, dotted ids,
  embedded source comment markers and the kept names: Orca Cloud, Orca Cube,
  Orca String Hell, Orca Tolerance Test, Orca YOLO, Orca Arena, Orca Palette,
  Orca Badge, OrcaSliced Combo, Orca Preset Bundle, Orca Filament Library
  (they name an upstream service, a built-in model or calibration, or a
  format). Identifiers the name runs into (`OrcaSlicerVersion`,
  `ORCA_CAD_GLYPH`) never match, and neither does a name followed by a
  combining mark ("Orca" + U+0301 is another word). All capitals count as
  one name: "ORCA SLICER" and "ORCASLICER" become "CosmoSlice".
- Names derived from the app key point at real files and folders, which keep
  the key (decision 0133): `OrcaSlicer.conf`, `OrcaSlicer.app`,
  `OrcaSlicer.AppImage` and a Windows folder after a backslash
  (`%APPDATA%\OrcaSlicer`, `...\Roaming\OrcaSlicer`) are never renamed.
- Inflected languages glue a suffix to the name (cs "OrcaSliceru", hu
  "OrcaSlicerrel", eu "OrcaSlicerren", sv "OrcaSlicers"). In a translation, a
  name followed by lowercase Latin letters is an inflected name (a Korean or
  Japanese particle is not: it is not Latin). The suffix depends on the new
  name, so it is never guessed: `inflections.json` rows
  `{"language", "old", "new", "source"}` give, per catalogue language, the
  exact text `old` and its `new` text, written by a speaker of that language.
  `old` is the inflected form (cs "OrcaSliceru"), or a phrase around the
  name, inflected, plain or hyphenated, when a word next to it must change
  too: the Hungarian article ("az OrcaSlicer" -> "a CosmoSlice", since az
  only goes before a vowel) or a Basque suffix that follows the new name's
  sound ("Orca-ren" -> "CosmoSlice-en", "OrcaSlicer-etik" ->
  "CosmoSlice-tik"). The bare plain name is never a row: the plain rule
  renames it. Rows match whole words only (never after or before another
  letter or digit, never through part of a longer name or across a URL,
  file or kept name) and only in their language; they are applied longest
  first, so "az OrcaSlicerrel" goes before "az OrcaSlicer" and no text is
  renamed twice, then the plain rule runs. An inflected name without a row
  stays and G8 reports it (decision 0135). In English text (C++ sources, msgids) "Orcas" stays another word.
  `just brand-name-inflections` lists every form still without a row, per
  language, with an example. Hyphenated forms ("OrcaSlicer-ben") are renamed
  by the plain rule ("CosmoSlice-ben") and listed apart, for a speaker to add
  a row only where the suffix must change.
- Refresh against DEV: 48 of CosmoSlice's 76 pairs still match (28 dropped:
  their text is gone upstream); 64 msgid rows and 9 literal rows were added
  for text upstream added since, 121 rows in all. `just brand-name-candidates`
  proposes rows for what later upstream merges bring.
- The renamed catalogues compile with `msgfmt --check-format` (checked on a
  scratch copy of DEV).

## Consequences

- Translations stay visible after the rename; a translation that words the
  name differently than the rule finds keeps it (guard G8 reports a confirmed
  translation of a renamed msgid that still names the product).
- Removing it: delete `rename.json`; the patches alone leave many texts
  saying OrcaSlicer.
