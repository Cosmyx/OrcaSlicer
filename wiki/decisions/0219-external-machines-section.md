# 0219. External machines section in Preferences

## Status

Accepted.

## Context

Upstream's Online tab of Preferences has two toggles for Bambu Lab services:
"Enable Bambu Cloud" (section "Cloud Providers", bound to the `bbl` cloud
provider of the app config) and "Enable Bambu network plug-in" (section
"Bambu network plug-in", key `installed_networking`, which on Windows also
offers to download the plug-in). Cosmyx does not test or support these
modules nor the machines they drive, and users must know that before turning
one on. `Preferences.cpp` is edited often upstream, so it may only get
one-line hooks (decision 0002).

## Decision

- Upstream builds both rows unchanged. One call line after the network
  plug-in version row, `Cosmyx::setup_external_machines(g_sizer,
  item_bambu_cloud, item_enable_plugin)`, plus one include line after the
  last include of the file, hand the Online tab sizer and the two row sizers
  to `src/slic3r/GUI/Cosmyx/ExternalMachinesPrefs.{hpp,cpp}`. That is the
  whole upstream diff: two lines tagged `// Cosmyx`.
- The helper renames the "Bambu network plug-in" section title to
  "External machines" and moves the Bambu Cloud row into it, above the
  plug-in toggle. The section reads: Enable Bambu Cloud, Enable Bambu network
  plug-in, Network plug-in version. The version selector stays: it belongs to
  the plug-in. The "Cloud Providers" title is destroyed when the Bambu Cloud
  row was its only row; it is not merely hidden, because switching tabs shows
  every item of the page again.
- The helper only reads the shape upstream gives the page (a row is a sizer
  holding a `CheckBox`, a title is a sizer holding a `StaticLine`). When that
  shape is not found it logs a warning and leaves the layout as upstream
  built it; the warnings on the toggles still apply.
- Re-creating the two rows in the Cosmyx file behind a hook that skips
  upstream's adds was rejected: it would copy upstream's handlers (stealth
  mode interplay, homepage refresh, plug-in download) and drift from them.
  Moving the existing rows keeps every upstream behaviour: the stealth mode
  disabling Bambu Cloud, the plug-in install prompt, the restart prompts.
- Each checkbox gets a second `wxEVT_TOGGLEBUTTON` handler, bound after
  upstream's, so wx calls it first (dynamic handlers run in reverse order of
  binding). Turning a toggle on shows a warning `MessageDialog` ("External
  machines", buttons Enable and Cancel): Enable passes the event on to
  upstream's handler, Cancel, Escape or the close box put the checkbox back
  off and stop the event, so the setting is never written. Turning a toggle
  off never asks. The rule is the pure function
  `external_toggle_outcome()` in `logic/ExternalMachines.{hpp,cpp}`, tested by
  `tests/cosmyx/test_cosmyx_external_machines.cpp`.
- A setting already on (from an earlier version or the config file) is shown
  on without a warning; only a click asks.
- The strings are extracted into `localization/cosmyx/external-machines/`
  (decisions 0081, 0085). French is translated; the other languages are left
  to the per-language translation pass. "Enable" is an OrcaSlicer string and
  stays out of the template (decision 0084).

## Consequences

- The GUI golden of the Online tab of Preferences changes with this branch.
- An upstream rename of the rows or titles needs no Cosmyx change; an
  upstream change of their sizer shape makes the helper log a warning and
  leave the layout alone.
- The hook lines are pinned by `scripts/cosmyx/tests/test_external_machines.py`.
- Removing it: delete the two hook lines in `Preferences.cpp`,
  `ExternalMachinesPrefs.{hpp,cpp}`, `logic/ExternalMachines.{hpp,cpp}`, their
  tests and `localization/cosmyx/external-machines/`.
