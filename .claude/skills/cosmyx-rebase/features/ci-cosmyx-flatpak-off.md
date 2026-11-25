# ci/cosmyx-flatpak-off (PR #113)

## Purpose

The fork ships no Flatpak and the leg was often red for upstream reasons, so the Flatpak build and its two unit test jobs are
skipped unless the repository variable `COSMYX_FLATPAK` is `true`. Decision 0213, changelog slot T19 (`### CI-release`,
flagged **Removed**).

## Parent and dependencies

- Parent: `chore/cosmyx-foundation` (PR #86). Range: `eea6362f51` (the gate, test, decision, slot), `e2e6aba26f` (changelog
  PR link).
- Upstream fact: on DEV the Flatpak job lives in `.github/workflows/build_flatpak.yml` (upstream `a4de8cb891`, #17202),
  called by `build_all.yml` and `build_optional.yml`; the two unit test jobs `needs:` the `flatpak` job.

## Changes

| File | Kind | What the change does |
|---|---|---|
| `.github/workflows/build_flatpak.yml` | upstream hook (1 line) | `    if: ${{ vars.COSMYX_FLATPAK == 'true' }} # Cosmyx: off unless the repo variable turns it on (decision 0213)` added after `name: Build Flatpak` of the `flatpak` job. No upstream line edited. |
| `scripts/cosmyx/tests/test_flatpak_off.py` | test | `FlatpakOffTests`: the job is gated by the variable, the gate is one tagged line, the unit test jobs still need the `flatpak` job. |
| `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md` | foundation files | `T19` added to `CI-release`. |
| `wiki/decisions/0213-flatpak-build-off.md` | docs | Decision. |
| `CHANGELOG.md` | data | Line under the new `<!-- cosmyx-slot: T19 -->`. |

## Rebase risk zones

- On `v2.5.1` / `v2.5.2` there is no `build_flatpak.yml`: the `flatpak:` job sits in `build_all.yml` (see the modify/delete
  entries of `conflits.md`). Put the same one `if:` line on that job there; do not edit the upstream `if:` of `build_all.yml`
  callers (ten upstream commits on that line, decision 0213).
- If upstream adds its own `if:` to the `flatpak` job, the two keys collide: merge them into one expression, still tagged.

## Intent to preserve

- One added, tagged line; the leg comes back with the variable alone, no code change.
- The foundation's flatpak test-asset hook (decision 0005) stays, so the leg works when turned on.

## Verification

- `just test-scripts` (`test_flatpak_off.py`, slot checks); `just decisions`.
- In a `build_all` run without the variable, "Build Flatpak" and the Flatpak unit tests show as skipped.

## Known pitfalls

- Slot union: the integration merge conflicts with every sibling slot (T15, T16a in `CI-release`); resolve by union.

## Shared files with other branches

- `.github/workflows/build_flatpak.yml`: foundation (flatpak fixes), product-name (`flatpak` package-name step before
  "Upload artifacts Flatpak"). Different anchors; keep all.
- `CHANGELOG.md` (T19), `test_foundation.py`, decision 0003.
