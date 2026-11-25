# 0020. CHT nozzle enum value in the middle of NozzleType

## Status

Accepted.

## Context

The CHT nozzle needs a `NozzleType` value and a `nozzle_type` choice ("cht",
label "CHT"). The settings page edits `nozzle_type` (a `coEnums` option) with a
combo box. For enum options that are not on its hard-coded list,
`Choice::get_value()` stores the selected position as the enum value
(`src/slic3r/GUI/Field.cpp`, `get_value()` and `set_value()`), and
`nozzle_type` is not on that list. So the position of "cht" in
`enum_values` must equal `int(NozzleType::ntCHT)`, or picking CHT in the GUI
saves another nozzle type.

Appending CHT after `ntE3D` (value 6) would need a position 6 in a five-item
list. `ntE3D` is not a `nozzle_type` choice: it is absent from `enum_values`
and from `s_keys_map_NozzleType`, configs store nozzle types as strings, and
the device code maps E3D by string (`DevNozzleSystem.cpp`,
`PrintOptionsDialog.cpp`).

## Decision

- `ntCHT` is inserted in `CommonDefs.hpp` between `ntBrass` and `ntE3D`, so it
  takes value 5, the next free choice position. `ntE3D` moves to 6 and
  `ntCount` to 7; nothing stores or indexes by their numeric value.
- `Cosmyx::extend_cht_nozzle()` (`src/libslic3r/Cosmyx/ChtNozzle.cpp`) inserts
  "cht" / "CHT" into `nozzle_type` at index `int(ntCHT)` (clamped to the list
  size), not at the end. It does nothing if "cht" is already there.
- The string maps get "cht": `NozzleTypeEumnToStr`, `NozzleTypeStrToEumn`
  (`PrintConfig.hpp`) and `s_keys_map_NozzleType` (`PrintConfig.cpp`), each
  on its own line right after the `undefine` entry, ending with `// Cosmyx`.
- `resources/info/nozzle_info.json` gets `"cht": 65` (HRC) as the first entry
  of `nozzle_hrc`. JSON has no comments, so this line cannot carry the
  `// Cosmyx` marker; this decision records it instead.
- Upstream tungsten carbide (HRC 85) is kept unchanged.
- The label "CHT" is a product acronym, which the localization glossary keeps
  in English, so `ChtNozzle.cpp` is not added to `localization/i18n/list.txt`
  (an upstream file).

## Consequences

- If upstream adds a nozzle type before `ntE3D`, our `ntCHT` value would clash
  in position: `tests/cosmyx/test_cht_nozzle.cpp` checks that every choice sits
  at its enum value and that "cht" sits at `int(ntCHT)`, so the clash fails
  the tests instead of silently saving the wrong type.
- Removing CHT means deleting the five hook lines (one enum value, three map
  entries, one JSON entry), emptying `extend_cht_nozzle()` and deleting its
  tests. Configs that saved `nozzle_type = cht` would then fail to load the
  value and fall back to the default.
