# 0173. Every NativeCommands catalog key is classified

## Status

Accepted.

## Context

`NativeCommands::catalog()` lists about a hundred commands; some open dialogs,
others open native file dialogs or the browser, and upstream adds new ones.

## Decision

- `script.json` `menu_items` classifies every catalog key: `dialog` (capture
  the window it opens), `view` (capture the main window), `toggle` (capture,
  then run it again), `any` (a window if one opens, else the main window) or
  `skip` with a reason (native file dialog, browser, network, account, or run
  by another step). Rules may name a `section`, a `param`, a `revert` command
  and `restore` (reload the fixture afterwards).
- An unclassified key, or a rule naming a removed key, fails the pass (the
  driver checks the live catalog) and the script tests (which read the
  catalog from `NativeCommands.cpp`).

## Consequences

- A new upstream command fails the goldens until it is classified: one line in
  `script.json`.
