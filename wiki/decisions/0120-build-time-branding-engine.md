# 0120. The branding is applied at build time from tables

## Status

Accepted.

## Context

The Cosmyx build must look like CosmoSlice (logos, colours, product name)
while merging upstream OrcaSlicer into `DEV` stays conflict-free. Editing the
upstream images, colours and strings in git would conflict on every upstream
change to them. CMake installs `resources/` whole, so replacement files kept
inside it would ship next to the originals.

## Decision

- The branding lives in tables under `cosmyx-src/branding/`: the image
  manifest (`manifest/<group>.json`), the vendored files
  (`overlay/<repository-relative path>`), and later `colours.json` and
  `product-name/`.
- `scripts/cosmyx/branding/cli.py apply` brands the checked-out tree in a
  fixed order: pre-guards, overlay, colours, product name, post-guards, then
  the report (`build/cosmyx/branding-report.json`, and the step summary in
  CI). Standard library only, Python 3.9 or newer.
- Every file is backed up under `build/cosmyx/branding-state/` before its
  first write. A failed pre-guard writes nothing; a stage or post-guard
  failure restores the backups at once; `revert` restores the exact bytes and
  deletes the files the overlay created. Applying a branded tree reverts it
  first, so apply is idempotent.
- The CI runs it in `.github/actions/cosmyx-prepare`, after the translation
  graft and before the hide step (decision 0087), so a branded build is not
  marked `-dirty`. The branding tests run in the same action first.
- The colour and product-name stages apply their table rows with the shared
  counted text patcher, then call an optional plugin module of the package
  (`colours`, `product_name`) exposing `apply(ctx, backup)` and
  `guards(ctx, phase)`.
- Local checkouts keep the Orca branding: `just brand-apply` and
  `just brand-revert` brand and restore a checkout by hand.
- `scripts/cosmyx/just/branding.just` holds the engine recipes and ends with
  one `import?` line per branding sub-task (`branding-logos.just`,
  `branding-colours.just`, `branding-candidates.just`,
  `branding-product-name.just`). A sub-task adds its recipes in its own file
  and never edits `branding.just`, so its branch merges with the others in
  any order without a conflict; a missing file is simply not loaded.

## Consequences

- No upstream file is edited in git for the branding; the only hook is the
  existing prepare action.
- The build tree differs from git; `just worktree-hidden` shows the edited
  files on a CI checkout.
- Removing it: delete the "Apply Cosmyx branding" step and the test line in
  the prepare action, `scripts/cosmyx/branding/`, `cosmyx-src/branding/`,
  `scripts/cosmyx/just/branding*.just` and the wiki pages; builds then ship
  the OrcaSlicer branding.
