# 0178. What the first goldens leave out

## Status

Accepted.

## Context

Some surfaces need hardware, accounts or network, and some screens are too
deep to reach in the first set.

## Decision

- Deferred: other languages, another theme, the Device and Multi-device tabs
  and printer WebViews, calibration past the first screen, per-object
  settings, network error states, high DPI, Windows arm64 and Linux aarch64,
  plugin tabs. They are listed under `exclude` in `script.json` and in
  `surfaces.txt`.
- Native file dialogs and browser commands are skipped with their reason.
- The text caret: blink is off in the Linux image (GTK settings); on Windows
  and macOS a caret is within the tolerance. The driver does not move focus.

## Consequences

- Each deferred item is a script change plus its goldens when it is taken up.
