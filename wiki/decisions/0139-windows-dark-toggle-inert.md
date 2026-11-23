# 0139. The Windows dark mode toggle is left in place but has no effect

## Status

Accepted.

## Context

Windows Preferences shows an "Enable dark Mode" checkbox
(`PreferencesDialog::create_item_darkmode()`); macOS and Linux have none.
With dark mode always on (decision 0136) the toggle must have no effect. It
can be hidden, which needs one more hook in `Preferences.cpp`, or left inert.

## Decision

The toggle stays visible and inert. Clicking it writes `"0"`, then calls
`Update_dark_mode_flag()`, which calls the forced `dark_mode()`: the key is
healed back to `"1"` (decision 0137) and the following
`force_colors_update()` re-applies dark. The checkbox reads `"1"` each time
the dialog opens, so it shows as checked again.

No hook is added to `Preferences.cpp`, which upstream edits often.

## Consequences

- A Windows user can untick the box and see nothing change until the dialog
  is reopened, where it shows ticked again. This is a minor oddity, judged
  less costly than one more upstream hook.
- Hiding it later is one hook around the `create_item_darkmode()` call in
  `PreferencesDialog`, recorded in a new decision that supersedes this one.
