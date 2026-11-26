# feat/cosmyx-profiles (PR #126)

Analysed commits: `origin/feat/cht-nozzle..origin/feat/cosmyx-profiles`, no merges (8 commits: the foundation's `92830e0a8b`, `41b887876e`, `be423c6998`, not in cht-nozzle, then the branch's own `c260ac5399`, `a08022c381`, `3355deb0e8`, `28147361a5`, `6cec6056d0`). The branch starts from `chore/cosmyx-foundation` (`be423c6998`) and merges `origin/feat/cht-nozzle` (`08d8d62f96`) in `2d95cdf9b8`. Compared with `origin/DEV` and `upstream/v2.5.2`.

## Purpose

Adds the Cosmyx vendor bundle: the eight Cosmyx printer models (Nova, Nova can-out, Nova Haute Temperature, Nova Double Tete, Nova Metal Ceramique, SuperNova, SuperNova Double Tete and its Metal Ceramique version) with four nozzles each, their processes and filaments, from the 2.3.1 fork's standard line, as bundle version `02.00.00.00`. The Cosmyx bed type is dropped: every printer defaults to the Textured PEI Plate. Preset names are kept so user presets made from the old pack still find their parents; setting and filament ids are new (decision 0224). Changelog slot T30, in a new `profiles` area.

## Parent and dependencies

- Parent: `feat/cht-nozzle` (PR #89), merged into the branch: 20 machine files set `nozzle_type` to `cht` (scalar or per-extruder array), a value only #89 defines. Without it the loader refuses those presets.
- The integrate tool's own commits are `merge-base(cht-nozzle)..tip` without merges: the three foundation commits after `39c40f609f` come along because cht-nozzle sits on the older foundation. In a replay onto a rebased foundation they are already applied: `92830e0a8b` and `41b887876e` conflict on `scripts/cosmyx/tests/test_foundation.py` and `CHANGELOG.md` (the same as for `feat/cosmyx-languages`); rerere resolves them, otherwise take the foundation version.
- Consumers: `feat/cosmyx-machine-hook` (PR #125) detects a Cosmyx machine by this bundle's vendor id `Cosmyx`.

## Changes

| File | Kind | What it does |
|------|------|--------------|
| `resources/profiles/Cosmyx.json` | Cosmyx-owned (new file in an upstream folder) | Vendor index, `name` and `id` `Cosmyx`, version `02.00.00.00`. |
| `resources/profiles/Cosmyx/**` | Cosmyx-owned (new folder) | Machine models and machines, processes, filaments, model covers (164 files). |
| `.github/workflows/cosmyx-checks.yml` | foundation file | Adds `resources/profiles/Cosmyx/**`, `resources/profiles/Cosmyx.json`, `scripts/orca_profile_tool.py` to both `paths:` lists. |
| `scripts/cosmyx/tests/test_cosmyx_profiles.py` | test | Runs the upstream profile tool check on the bundle; vendor id and major version, eight models with their cover, index paths with their exact case. |
| `tests/cosmyx/test_cosmyx_profiles.cpp` | test | Loads the bundle through `PresetBundle`; every printer resolves its default presets. |
| `scripts/cosmyx/tests/test_foundation.py`, `wiki/decisions/0003-changelog-slots.md` | foundation data | New `profiles` area with T30; the three checks paths required. |
| `wiki/decisions/0224-cosmyx-vendor-profiles.md` | data (docs) | The decision. |
| `CHANGELOG.md` | data (docs) | New `profiles` area in the rules and at the end of the period (after `CI-release`), one line under `<!-- cosmyx-slot: T30 -->`. |

No upstream file is edited: upstream has no `Cosmyx` vendor, so the bundle can never conflict with an upstream merge.

## Rebase risk zones

| Upstream file / function | In v2.5.2 | DEV vs v2.5.2 | Churn 2026 |
|--------------------------|-----------|---------------|-----------|
| Profile schema (`PrintConfig.cpp` keys, `PresetBundle` loader, `orca_profile_tool.py` checks) | bundle checked against DEV's tool | new upstream checks may flag the bundle | high |
| `nozzle_type` enum | `cht` from #89 | see the cht-nozzle sheet | see the cht-nozzle sheet |

The dry run onto `v2.5.2` replays the 8 commits with rerere only.

## Intent to preserve

- Vendor id exactly `Cosmyx` (the machine hook depends on it), bundle files only under `resources/profiles/Cosmyx*`.
- Preset names unchanged; any change to a profile bumps `version` in `resources/profiles/Cosmyx.json`.
- No Cosmyx bed type; every printer's `default_bed_type` is the Textured PEI Plate on the bundle's machine base.

If upstream changes the profile schema or the checks: fix the bundle files and bump the bundle version; never edit upstream's tool or loader.

## Verification

`just test-scripts` (profile tool checks, slot list, checks paths); Catch2 `tests/cosmyx/test_cosmyx_profiles.cpp` (`ctest --test-dir build -C Release -R cosmyx --output-on-failure`); `just decisions`; upstream's `scripts/orca_profile_tool.py check` on the vendor. Manual: add a Cosmyx printer in the setup wizard, check the CHT nozzle and the Textured PEI Plate.

## Known pitfalls

- Parented on the foundation instead of cht-nozzle, the tool would replay cht-nozzle's 3 commits a second time.
- The `profiles` area is the last one of the period: a branch adding an area after `CI-release` conflicts there; keep both, `profiles` in the area order of the rules.
- `test_foundation.py` `SLOTS_BY_AREA` gains a `profiles` key and the checks path list three entries: union with other branches' additions.

## Shared files with other branches

- `.github/workflows/cosmyx-checks.yml` (union of `paths:`), `CHANGELOG.md` (area rules and slot T30), `test_foundation.py` and decision 0003 (union of slots and areas), `wiki/decisions` number 0224.
