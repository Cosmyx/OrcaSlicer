# 0134. Literals and msgids are renamed together, never fuzzy

## Status

Accepted. Replaces CosmoSlice D-004's fuzzy marking for this fork.

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
  `ORCA_CAD_GLYPH`) never match.
- Refresh against DEV: 48 of CosmoSlice's 76 pairs still match (28 dropped:
  their text is gone upstream); 64 msgid rows and 10 literal rows were added
  for text upstream added since, 122 rows in all. `just brand-name-candidates`
  proposes rows for what later upstream merges bring.
- The renamed catalogues compile with `msgfmt --check-format` (checked on a
  scratch copy of DEV).

## Consequences

- Translations stay visible after the rename; a translation that words the
  name differently than the rule finds keeps it (guard G8 reports a confirmed
  translation of a renamed msgid that still names the product).
- Removing it: delete `rename.json`; the patches alone leave many texts
  saying OrcaSlicer.
