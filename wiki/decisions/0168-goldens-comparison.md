# 0168. Linux goldens are byte-exact, Windows and macOS use a tolerance

## Status

Accepted.

## Context

The shared rules say any byte of difference fails. That holds on Linux, where
everything is pinned, but not on hosted Windows and macOS runners: system
widgets, font smoothing, WebView2 and the macOS GPU change with runner images.
The user accepted a recorded exception for those two OSes.

## Decision

- Linux: byte-exact.
- Windows and macOS (`tests/cosmyx/gui/tolerance.json`): a pixel differs when
  one channel moves by more than 8; an image fails when more than 0.05 % of
  its pixels differ, when one 16x16 tile has more than 10 % of its pixels
  differing, or when its size changed.
- Text goldens (menu tree, WebView text, `surfaces.txt`) are byte-exact on
  every OS. `environment.json` is reported as drift, never compared.
- A golden missing from the committed set fails, so a new screen cannot ship
  without its golden.

## Consequences

- Small regressions below the tolerance can pass on Windows and macOS; Linux
  catches them for everything that is not OS-specific.
- Tightening the tolerance is a change of `tolerance.json` only.
