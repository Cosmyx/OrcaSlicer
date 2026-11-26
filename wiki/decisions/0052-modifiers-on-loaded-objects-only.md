# 0052. Calage 3 modifiers apply to the loaded objects only

## Status

Accepted.

## Context

The previous menu, after loading "Calage 3 SNDT", removed the parameter
modifiers of every object on the plate and added the preset boxes to each of
them, so the objects the user already had were changed too. It also erased the
removed volumes from the list without deleting them.

## Decision

- `Plater::load_files()` returns the indices of the objects it loaded; only
  those objects get the preset's boxes.
- `apply_calibration_modifiers()` (wxWidgets-free) removes the object's
  parameter modifiers, deleting them, and adds one modifier volume per box with
  the box's settings, `extruder` 0 when the box sets none, and
  `is_from_builtin_objects`. It does not use `ModelObject::delete_volume()`,
  which folds the last volume's transform into the instances and would move
  the frame the boxes are placed in.
- Boxes keep the old placement: rotate about X, then Y, then Z, translate in the
  rotated frame. A negative size component is built as a positive cube shifted
  towards the negative side, which spans the same space but keeps the facets
  facing outwards (the old code built that box inside out).
- The base settings of the preset are offered in a yes/no dialog, as before;
  only the keys that differ from the print preset are changed.
- The change is one undo snapshot.

## Consequences

- Tests cover the parsing of the shipped JSON, the box bounding box and its
  positive volume, and that another object's modifier is left untouched.
- Removing it: see decision 0050.
