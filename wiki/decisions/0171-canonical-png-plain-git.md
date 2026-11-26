# 0171. Canonical PNG goldens in plain git

## Status

Accepted.

## Context

Goldens must be byte-stable and reviewable, and upstream's `.gitattributes`
rules out LFS without editing an upstream file.

## Decision

- PNG files are written canonically: 8-bit RGBA, filter 0, zlib level 9,
  only IHDR, IDAT and IEND (no time, no gamma, no text).
- Layout: `tests/cosmyx/gui/goldens/<os>/NN-slug.png`, `NN-slug.txt` text
  goldens, `surfaces.txt`, `environment.json`.
  `tests/cosmyx/gui/goldens/.gitattributes` marks PNG binary and text LF.
- Plain git, no LFS (user answer): about 20-40 MB per OS for the first set.

## Consequences

- The repository grows with every refresh; only failed goldens are rewritten
  (decision 0172), so unchanged screens never add a blob.
