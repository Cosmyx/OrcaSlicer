# 0051. Cosmyx model files under resources/cosmyx

## Status

Accepted.

## Context

The previous branch stored its models in `resources/handy_models/cosmyx/` and
its calibration preset in `resources/calibration/`, both upstream folders,
with mixed-case names and one name with spaces ("Support bobine droit.3mf").
`handy_models_dir()` also remembers the last folder used, and a Cosmyx subfolder
of `handy_models` would be stored as such.

## Decision

- The files are copied byte for byte from the `cosmyx-2.3.1-7` tag (same git
  blob ids) into a folder upstream does not have:
  - `resources/cosmyx/models/`: `cosmyx_cube.3mf`, `cube_bi_couleur.3mf`,
    `support_bobine_droit.3mf`, `control_tension_belt.stl`;
  - `resources/cosmyx/models/calibration/`: `calage_1_nova.3mf`,
    `calage_1_sndt.3mf`, `calage_2_sndt.3mf`, `calage_3_sndt.3mf`;
  - `resources/cosmyx/calibration/calage_3_modifiers.json`.
- Names are lowercase, with underscores and no spaces, so they are safe on
  every file system and never differ only by case.
- The menu icon keeps its name, `resources/images/menu_add_part_cosmyx.svg`,
  because the icon loader only looks in `resources/images/`.
- Nothing is installed by hand: every platform installs the whole `resources/`
  folder.

## Consequences

- A test checks that every catalogue path exists, is lowercase and has no
  spaces.
- Projects that referenced the old paths are not affected: the models are
  loaded as geometry and the project keeps no link to the file.
