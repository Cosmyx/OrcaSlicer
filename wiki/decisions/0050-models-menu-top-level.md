# 0050. Cosmyx 3D models as a top-level menu

## Status

Accepted.

## Context

The previous Cosmyx branch showed a "Cosmyx 3D Models" item next to "Add
Handy models" in the empty-space context menu and in the plate menu. The plan
offered to nest it inside "Add Handy models" to save a hook; the user chose to
keep it top-level, as before.

`MenuFactory::update_default_menu()` rebuilds the default menu in place: it
destroys the items it knows by label ("Add Primitive", "Add Handy models",
"Show Labels") and calls `create_default_menu()` again. A new top-level item
missing from that list would be appended a second time on every refresh.

## Decision

- `Cosmyx::append_models_submenu(wxMenu* menu, wxWindow* parent)` appends the
  "Cosmyx 3D Models" submenu with three groups: "Calibration Models Dual Head",
  "Calibration Models Single Head" and "Cosmyx Handy Models".
- The function is idempotent: it remembers the id of the item it added to each
  menu and destroys that item before appending a new one. The item is found by
  id, never by its translated label, and gets a fresh id each time so the
  update-UI handler bound for the old item never reaches the new one.
- Because of that, `update_default_menu()` needs no hook. `GUI_Factories.cpp`
  gets three lines only, each ending with `// Cosmyx`:
  - line 2: `#include "Cosmyx/CosmyxModelsMenu.hpp" // Cosmyx`
  - in `create_default_menu()`, right after the "Add Handy models" append:
    `Cosmyx::append_models_submenu(&m_default_menu, m_parent); // Cosmyx`
  - in `create_plate_menu()`, right after the "Add Handy models" append:
    `Cosmyx::append_models_submenu(menu, m_parent); // Cosmyx`
- The include names the feature header directly rather than
  `Cosmyx/Cosmyx.hpp`, so this branch and the other GUI branches never edit the
  same shared header.

## Consequences

- After an in-place rebuild the Cosmyx item is appended again right after the
  new "Add Handy models" item, so its position follows upstream's own order.
- Removing the feature: delete the three hook lines, `CosmyxModelsMenu.*`,
  `logic/CosmyxModels.*`, `resources/cosmyx/`, the icon and the test file.
