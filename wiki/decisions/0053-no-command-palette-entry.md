# 0053. No command palette entries for the Cosmyx models

## Status

Accepted.

## Context

Upstream lists its handy models in the command palette by looping over
`MenuFactory::handy_models()`. Adding the Cosmyx models there would need a hook
in the palette code, and the previous Cosmyx branch had no such entry.

## Decision

The Cosmyx models are reachable from the context menus only.

## Consequences

- No hook in the command palette files.
- Adding them later means one call in the palette loop over `cosmyx_models()`,
  which already holds the labels and the actions.
