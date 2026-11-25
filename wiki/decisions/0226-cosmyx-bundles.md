# 0226. Cosmyx bundles 8 and 9

## Status

Accepted.

## Context

Cosmyx ships as numbered bundles (releases). Bundle 7 was built on an older
OrcaSlicer; its features have since been rebased on OrcaSlicer 2.5.2 as
separate pull request branches, next to branches that add new features. The
teams validate bundle 8, so it must not carry anything they have not
validated, while the new features keep moving towards bundle 9. The
integration tool (decision 0215) built only one integration with every
branch of `scripts/cosmyx/integrate/branches.json`.

## Decision

- Bundle 8 holds only the bundle-7 features rebased on OrcaSlicer 2.5.2 plus
  the new integration and build tooling: `chore/cosmyx-foundation`,
  `ci/cosmyx-upstream-sync`, `feat/cht-nozzle`, `feat/ironing-temperature`,
  `fix/toolchange-fan-order`, `feat/cosmyx-models`, `feat/cosmyx-version`,
  `feat/cosmyx-stealth-mode`, `feat/cosmyx-translations`,
  `feat/cosmyx-translations-fill`, `feat/cosmyx-windows-signing`,
  `feat/cosmyx-update-check`, `feat/cosmyx-profiles`,
  `feat/cosmyx-machine-hook`, `ci/cosmyx-artifact-checks`,
  `ci/cosmyx-macos-signing`, `ci/cosmyx-exec-smoke`, `ci/cosmyx-flatpak-off`,
  `ci/cosmyx-integrate`, `ci/cosmyx-mac-retry`, `ci/cosmyx-dev-build`,
  `docs/cosmyx-changelogs`, `docs/cosmyx-rebase-skill`.
- Every other branch, and every new feature from now on, goes to bundle 9.
- Every row of `branches.json` carries an integer `bundle`, the bundle that
  first ships the branch. A row without one is refused, and so is a branch
  whose parent is in a later bundle (a branch cannot ship before its parent).
- `just cosmo-integrate [BASE] --bundle N` (and `cosmo-rebase-check`) keeps
  only the rows of bundle N or an earlier one, then runs the parent checks
  again on that subset. Without `--bundle`, every row is kept, as before.

## Consequences

- A bundle-8 integration is built with `just cosmo-integrate origin/DEV
  --bundle 8`, with no hand-made `--skip` list.
- A new branch row needs its `bundle`; the shipped-list tests pin the bundle-8
  set, so moving a branch between bundles is a visible change of that test.
- A hidden dependency of a bundle-8 branch on a bundle-9 branch (a file or a
  test that only a bundle-9 branch provides, outside the parent chain) is not
  caught by the list checks; it shows up in the gates of a `--bundle 8`
  integration and is fixed in the branch concerned.
- Removing it: drop the `bundle` fields, `select_bundle` and the `--bundle`
  option of `scripts/cosmyx/integrate/cli.py` and their tests.
