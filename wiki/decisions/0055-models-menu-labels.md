# 0055. Labels of the Cosmyx models menu

## Status

Accepted.

## Context

The previous branch's code and its translation template disagreed on some
labels: the code showed "Calage 1 Nova", "Calage 2 SNDT" and "Calage 3 SNDT",
while the template held "Cosmyx Calage 1 Nova", "Cosmyx Calage 2 SNDT" and
"Cosmyx Calage 3 SNDT". The group submenus were not in the template, and one
of them was misspelt ("Calibrations Models Dual Head"). The dialog title
"Calibration Suggestion" was not marked for translation in the code.

## Decision

- Model labels keep the template's msgids, so existing translations still
  apply: "Calage 1 SNDT", "Cosmyx Calage 2 SNDT", "Cosmyx Calage 3 SNDT",
  "Cube Bicolore", "Cosmyx Calage 1 Nova", "Cosmyx Cube",
  "Control Tension Belt", "Support Bobine".
- The menu is "Cosmyx 3D Models"; the groups are
  "Calibration Models Dual Head", "Calibration Models Single Head" and
  "Cosmyx Handy Models" (spelling fixed, no translation is lost).
- The two dialog messages keep their old msgids word for word, and the title
  is translated with `_L("Calibration Suggestion")`.
- Catalogue labels are marked with `L()` in the wxWidgets-free catalogue and
  translated by the menu. Translations themselves are delivered by the
  translation task, not here.

## Consequences

- The translation extraction must include `src/slic3r/GUI/Cosmyx/` files.
