# 0223. Cosmyx models submenu on Cosmyx machines only

## Status

Accepted.

## Context

The "Cosmyx 3D Models" submenu (decision 0050) loads calibration models made
for Cosmyx printers. The user chose to hide it, not grey it out, when the
selected printer is not a Cosmyx machine (decision 0222), in both menus that
carry it: the empty-space context menu and the plate menu.

`MenuFactory` builds those menus once, in `MenuFactory::init()` while the
plater is created, and right-click only shows the prebuilt menu. Its
`update_default_menu()` rebuilds the empty-space menu in place. A printer
change must therefore edit the built menus; a check at popup time would need
new upstream lines.

## Decision

- `Cosmyx::append_models_submenu()` keeps one slot per menu: the parent
  window, the id of the item appended just before the call ("Add Handy
  models", the anchor), the index the submenu took, and the submenu item id
  while shown.
- When the menu is built, the submenu is appended only if
  `current_printer_is_cosmyx()` is true. The first preset load at startup
  then reaches the machine hook, which confirms or flips the state.
- The menu subscribes once to the Cosmyx machine flag. On a flip to false it
  destroys the submenu of every slot (found by id, never by label); on a flip
  to true it rebuilds it right after the anchor, or at the saved index
  (clamped) when the anchor is gone (`logic/MenuSlot.hpp`,
  `slot_insert_position()`). The submenu is rebuilt rather than detached and
  kept, so no menu item lives outside a menu and nothing leaks.
- The slots of a parent window are forgotten on its `wxEVT_DESTROY`: the
  menus are `MenuFactory` members that die with the plater inside that
  window, so a later notification must not reach them.
- The re-entry from `update_default_menu()` stays idempotent: the previous
  submenu is destroyed and the slot is taken again after the new anchor.
- No upstream line is added: the three `GUI_Factories.cpp` hooks of
  decision 0050 and the `Tab.cpp` hook of decision 0222 are enough.
- The menu and its gating are one branch, feat/cosmyx-models-cosmyx-only,
  based on the machine hook branch (feat/cosmyx-machine-hook): the menu is
  never shipped without its gating, so they share one pull request and one
  changelog line.

## Consequences

- On a printer that is not a Cosmyx machine, both context menus look like
  upstream's. A GUI golden of the empty-space or plate context menu taken on
  such a printer shows no Cosmyx submenu; one taken on a Cosmyx printer shows
  it after "Add Handy models". Goldens are regenerated on
  test/cosmyx-gui-goldens, not here.
- `tests/cosmyx/test_cosmyx_menu_slot.cpp` covers the reinsertion position;
  `scripts/cosmyx/tests/test_models_gating.py` pins the hooks and the gating
  wiring.
- Removing the gating: restore the unconditional append in
  `append_models_submenu()` and delete `logic/MenuSlot.*` and the two tests.
