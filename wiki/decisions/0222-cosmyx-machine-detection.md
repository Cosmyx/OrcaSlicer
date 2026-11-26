# 0222. Cosmyx machine detection and change hook

## Status

Accepted.

## Context

Some Cosmyx features only make sense on a Cosmyx printer (the Cosmyx models
submenu, a Cosmyx physical printer dialog). They need to know whether the
selected printer is a Cosmyx machine, and to hear when that changes. The user
chose the rule: the selected printer is a Cosmyx machine when its vendor is
Cosmyx. The Cosmyx printer bundle is `resources/profiles/Cosmyx.json`, so its
vendor id is `Cosmyx` (feat/cosmyx-profiles).

Upstream already resolves a preset's vendor:
`PresetCollection::get_edited_preset_with_vendor_profile()` walks the
`inherits` chain of the edited preset up to the first preset that carries a
vendor. A user preset saved from a Cosmyx system preset has no vendor itself
but inherits one; a custom printer with no system parent has none.

Printer changes all go through `Tab::load_current_preset()` of the printer
tab, which calls `Tab::on_presets_changed()`: selecting a printer in the
sidebar or the tab, saving, deleting or detaching a preset, the config wizard,
and the first load at startup (`GUI_App::load_current_presets()`, which runs
after the plater exists, so the early `plater() == nullptr` return of
`on_presets_changed()` does not skip it).

## Decision

- `src/libslic3r/Cosmyx/CosmyxMachine.{hpp,cpp}`:
  `is_cosmyx_vendor(const VendorProfile*)` compares the vendor id exactly
  (case-sensitive) to one constant, `COSMYX_VENDOR_ID = "Cosmyx"`; a null
  vendor is not Cosmyx. `is_cosmyx_printer(const PresetBundle&)` applies it to
  `printers.get_edited_preset_with_vendor_profile().vendor`. The vendor name
  is never compared, only the id (the bundle file name).
- `src/slic3r/GUI/Cosmyx/logic/FlipNotifier.{hpp,cpp}`: a wxWidgets-free
  cached boolean with subscribe / unsubscribe by handle. `update(value)` calls
  the listeners for the first value and for each flip, never for an unchanged
  value. Listeners may subscribe or unsubscribe from inside a call.
- `src/slic3r/GUI/Cosmyx/CosmyxMachineHook.{hpp,cpp}`:
  `current_printer_is_cosmyx()` reads `wxGetApp().preset_bundle` (false while
  there is none), `subscribe_printer_is_cosmyx()` /
  `unsubscribe_printer_is_cosmyx()`, and `notify_printer_changed()`, which
  feeds the current flag to one process-wide `FlipNotifier`. Subscribing does
  not call the listener: a consumer reads `current_printer_is_cosmyx()` when
  it builds its UI and then follows the flips.
- Upstream hook, `src/slic3r/GUI/Tab.cpp`, two lines tagged `// Cosmyx`:
  - after `#include "Tab.hpp"` (line 2; line 1 is a comment):
    `#include "Cosmyx/CosmyxMachineHook.hpp" // Cosmyx`
  - in `Tab::on_presets_changed()`, inside `if (m_type ==
    Preset::TYPE_PRINTER)`, right after `wxGetApp().switch_printer_agent();`:
    `Cosmyx::notify_printer_changed(); // Cosmyx`
  No second hook is needed for startup (see Context).
- The branch holds the hook only and is based on chore/cosmyx-foundation,
  so it does not depend on any consumer. Each consumer lives on its own
  branch: the models submenu gating (decision 0223) on
  feat/cosmyx-models-cosmyx-only, which merges this branch into
  feat/cosmyx-models (#92), and the Cosmyx physical printer dialog on
  feat/cosmyx-printer-connection, based on this branch.

## Consequences

- A printer bundle renamed away from `Cosmyx.json` turns every Cosmyx-only
  feature off; the constant and its test move with it.
- `scripts/cosmyx/tests/test_machine_hook.py` pins the two hook lines, their
  place and the startup path; `tests/cosmyx/test_cosmyx_machine.cpp` and
  `test_cosmyx_flip_notifier.cpp` cover the detection and the flip rule.
- Removing it: delete the two Tab.cpp lines, `CosmyxMachine.*`,
  `CosmyxMachineHook.*`, `logic/FlipNotifier.*` and their tests, after the
  consumers.
