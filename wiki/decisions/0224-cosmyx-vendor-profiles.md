# 0224. Cosmyx vendor profiles

## Status

Accepted.

## Context

The Cosmyx printers shipped with their own preset pack on the 2.3.1 fork
(lower-case vendor id `cosmyx`, bundle 01.07.00.18). That pack did not pass the
upstream profile checks (`scripts/orca_profile_tool.py check`): short names in
`default_materials`, old-style and Bambu-colliding ids, variant arrays not at
full width, files missing from the index and an index path whose case did not
match its folder (`nova_can_out` against `Nova_can_out`), empty
`compatible_printers` on instantiated filaments, and legacy keys. It also used
a Cosmyx bed type with its own pair of filament temperature keys, which needs
a code change upstream does not have.

## Decision

- The bundle is the vendor `Cosmyx`: `resources/profiles/Cosmyx.json` and
  `resources/profiles/Cosmyx/`. Upstream has no such vendor, so every file is
  new and merges from upstream cannot conflict.
- The source is the standard line of the 2.3.1 fork (bundle 7, can-out start
  G-code fix included): eight models, Nova, Nova can-out, Nova Haute
  Temperature, Nova Double Tete, Nova Metal Ceramique, SuperNova, SuperNova
  Double Tete and SuperNova Double Tete Metal Ceramique, with four nozzles each.
  The SuperNova Double Tete keeps the standard line defaults; its 0.4 nozzle
  default process is `0.20mm Standard @Cosmyx Common`.
- The Cosmyx bed type is dropped. `cosmyx_textured_bed_temp` and
  `cosmyx_textured_bed_temp_initial_layer` are removed from every filament
  (their values equal the plates' own temperatures), and every printer
  defaults to the Textured PEI Plate by its name, `default_bed_type` on the
  bundle's machine base. `default_bed_type` is a printer key: written on a
  `machine_model` it has no effect, so the models no longer carry it.
- Filaments that were open to every printer list every Cosmyx printer in
  `compatible_printers`, because upstream rejects an empty list on an
  instantiated vendor filament. Lists that named printers which do not exist
  (`Cosmyx X1`, `Cosmyx P1S`, `0.2 nozzle`) keep the printers that exist, the
  `0.2 nozzle` names mapped to the `0.25 nozzle` printers.
- `setting_id` and `filament_id` are minted by `orca_profile_tool.py
  generate-id`, replacing the old ids, some of which collided with Bambu ids.
  The pack is expected to be replaced by a new one later, so id continuity
  with the old pack is not kept.
- The preset-name translations of the old pack (`I18N/`) are not ported.
- Hand fixes the tool cannot make: `z_hop_types` "slope" becomes
  "Slope Lift" (the old value is not an enum value and stopped the Nova base
  from loading), `extruder_clearance_max_radius` is written under its current
  name `extruder_clearance_radius`, and the hotend model that never shipped
  (`cosmyx-3dp-hotend.stl`) is cleared.
- The printers use the CHT nozzle type, so the branch carries
  `feat/cht-nozzle`; without it no Cosmyx printer loads.
- The bundle version starts a new major, 02.00.00.00, for the new layout.
- `scripts/cosmyx/tests/test_cosmyx_profiles.py` runs the upstream check on
  the bundle and pins the choices above; `tests/cosmyx/test_cosmyx_profiles.cpp`
  loads the bundle as a system bundle and checks every printer's default
  process and filament. The Cosmyx checks workflow runs on bundle changes.

## Consequences

- The upstream validator built from upstream `main` does not know the CHT
  nozzle type, so its runs reject the Cosmyx printers; validate the bundle with
  a validator built from a branch that carries `feat/cht-nozzle`.
- The filaments that differ only by colour (CAPIFIL PLA, TECTONIC CPE) are
  kept as shipped; they go when the pack is replaced.
- Removing the bundle means deleting `resources/profiles/Cosmyx.json`,
  `resources/profiles/Cosmyx/` and the two tests; no other file depends on it.
