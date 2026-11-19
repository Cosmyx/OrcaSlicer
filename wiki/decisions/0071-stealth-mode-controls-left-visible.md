# 0071. Stealth mode controls left visible

## Status

Superseded by 0200.

## Context

With stealth mode forced at the getter (decision 0070), three upstream
controls still offer to change it: the "Stealth mode" checkbox in Preferences
(`Preferences.cpp`), the "Quit Stealth Mode" button of the login dialog
(`GUI_App.cpp`, the stealth-blocked login commands), and the stealth mode page
of the setup guide (`resources/web/guide/4orca/`).

## Decision

- The Preferences checkbox and the "Quit Stealth Mode" button stay visible and
  unchanged. They write the stored setting, which the getter ignores, so they
  have no effect: the checkbox shows checked again on the next opening, and a
  login started after "Quit Stealth Mode" never connects, because
  `on_user_login_handle()` and the sync paths still see stealth mode on.
- The guide page is not shown at all (decision 0073).
- Hiding them would need hooks in `Preferences.cpp` and `GUI_App.cpp`, in code
  upstream edits often, against the zero-conflict rule.

## Consequences

- A user can toggle a control that does nothing. This is accepted for now; a
  later change can hide them if users report confusion.
- Removing it: nothing to remove, the controls are upstream's.
