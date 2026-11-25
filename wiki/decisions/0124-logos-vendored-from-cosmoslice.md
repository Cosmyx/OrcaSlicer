# 0124. The logos are vendored byte for byte from CosmoSlice

## Status

Accepted.

## Context

The CosmoSlice fork already carries CosmoSlice-branded files under the
OrcaSlicer names (commits d317226e47 "Added CosmoSlice Logo", bab368d306
"Changed Logo Splash Screen" and 03d998431f for the Custom printer bed
texture). Assets are never drawn or approximated here: they are copied from a
source the user approved, or asked for.

## Decision

- Every CosmoSlice-branded file that replaces a `logos` row is copied byte for
  byte (`git show <commit>:<path>`, from the newest commit that touched it)
  into `cosmyx-src/branding/overlay/<path>`. Its row has source `cosmoslice`,
  `source_ref` `CosmoSlice@<commit>` and status `to-validate`.
- The overlay covers the application icon (window, taskbar, dock,
  executable, installer, Linux desktop and MSIX icons), the About dialog logos
  and the splash screen. The other `logos` rows (file-type icons, dialog,
  web and unreferenced logos) stay `missing` and the build keeps the Orca
  files for them.
- Files CosmoSlice does not provide stay `missing` and are asked for:
  `OrcaSlicer_horizontal_light.svg` and `OrcaSlicer_horizontal_dark.svg`
  (Troubleshoot dialog) and `resources/web/image/logo2.png` (unreferenced).
- Files CosmoSlice derived by its own tool (`.icns`) and the files this fork
  derives (decision 0125) come from the derivation, not from a copy.

## Consequences

- The user reviews and validates every row (decision 0121). The user
  validated the vendored and derived logos on 2026-11-24.
- Removing it: delete the overlay files and run `just brand-sync`; the rows go
  back to `missing` and the build keeps the Orca logos.
