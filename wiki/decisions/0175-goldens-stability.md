# 0175. A second pass proves the captures are stable

## Status

Accepted.

## Context

A flaky golden is a bug in the capture; the shared rules ask for a stability
check after captures change.

## Decision

- Two passes run when the workflow's `stability` input is `on`, or when it is
  `auto` and the built commit touches `tests/cosmyx/gui/`,
  `scripts/cosmyx/gui_goldens/` or the `Golden*` driver files (against DEV),
  in update mode, and on the weekly run.
- The second pass must match the first: byte-exact on Linux, within half the
  tolerance on Windows and macOS.

## Consequences

- Ordinary builds pay for one pass (30-45 minutes per OS).
