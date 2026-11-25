# 0218. Dev builds use the Cosmyx dev build workflow, release validation uses build_all

## Status

Accepted. Supersedes the `build_all.yml` hook of decision 0216.

## Context

Integration trees (every Cosmyx branch merged on a base) are built through a
draft pull request into a `cosmyx-ci/<BASE>` branch pushed at the exact base
commit (decision 0215). Decision 0216 made `build_all.yml` run on those pull
requests through a one-line hook in an upstream file, so the build ran in
upstream's pull request mode.

That build is not shaped for development:

- It always builds Linux (two archs), Windows and macOS arm64, whatever the
  change needs, and macOS x86_64 never.
- What it builds depends on the base: `build_all.yml` on tag v2.5.2 has no pull
  request mode, so it builds every arch, Flatpak included.
- It needs an edit to an upstream-owned workflow, against the zero-conflict
  rule (decision 0002).

The reusable workflows `build_all.yml` calls take the same inputs on DEV and
on v2.5.2: `build_check_cache.yml` (`os`, `arch`, `compiler`,
`build-deps-only`, `force-build`), `build_orca.yml` (`cache-key`,
`cache-path`, `os`, `arch`, `compiler`, `macos-combine-only`) and
`unit_tests.yml` (`os`, `artifact`, `test-dir`). They differ in what they
upload for macOS:

- DEV, pull request: a per-arch DMG `OrcaSlicer_Mac_<arch>_<ver>` (renamed
  `CosmoSlice_Mac_<arch>_<ver>` by the product-name hook, decision 0210).
- DEV outside a pull request, and v2.5.2 always: only the app bundle
  `OrcaSlicer_Mac_bundle_<arch>_<sha>`, meant for the universal job.

## Decision

- Dev builds use `.github/workflows/cosmyx-dev-build.yml` ("Cosmyx dev
  build"), a file of our own. `build_all.yml` stays untouched and remains the
  release validation build, with its full matrix.
- Triggers:
  - a pull request into `cosmyx-ci/**` (opened, synchronize, reopened,
    labeled, unlabeled). The labels `build:linux`, `build:windows`,
    `build:macos-arm64` and `build:macos-x86_64` pick the OSes; without any
    of them the build covers Linux, Windows and macOS arm64. A label event for
    a label outside `build:` starts nothing, and runs in a concurrency group of
    its own so it never cancels the running build. An unknown `build:` label
    fails the selection instead of falling back to the default, so a typo is
    seen.
  - `workflow_dispatch`, with one checkbox per OS (`linux`, `windows`,
    `macos-arm64` on, `macos-x86_64` off). GitHub shows the form only once the
    workflow is on the default branch (DEV); from then it runs on any ref
    through "Use workflow from". Until then, the pull request labels are the
    way to choose.
- One build per pull request (or ref), the newest cancelling the older.
- A `select` job runs `scripts/cosmyx/ci/dev_build.py select` (standard
  library, tested by `scripts/cosmyx/tests/test_dev_build.py`), and the build
  jobs call `build_check_cache.yml` and `unit_tests.yml` with the inputs
  `build_all.yml` passes, all of them present on both bases. Linux builds
  x86_64 and aarch64, Windows builds x64, macOS each chosen arch, and each
  build that ships tests runs them (macOS x86_64 builds none upstream). The
  base's own `build_orca.yml` runs, with the Cosmyx hooks the integration tree
  carries.
- A `macos_dmg` job per built macOS arch makes sure the run ends with
  `<product>_Mac_<arch>_<ver>` (`product` from the packages table, CosmoSlice
  on a base without it; `ver` as the build named its packages, through
  `scripts/cosmyx/cosmyx_version.py` when the tree has it). It keeps a DMG
  the build already uploaded, repacks upstream's per-arch DMG when only that
  one exists, and otherwise builds the DMG from the app bundle with upstream's
  `scripts/create_dmg.sh`.
- Before a repacked or packed app goes into its DMG, `dev_build.py seal-app`
  makes its signature verify. Upstream's unsigned build never seals the
  bundle: each Mach-O only carries the linker's ad-hoc signature and there
  is no `_CodeSignature`, so `codesign --verify --deep --strict` fails ("code
  has no resources but signature indicates they must be present") and
  Gatekeeper calls the downloaded app damaged. The step keeps a signature
  that already verifies, fails on an identity signature that no longer
  verifies, seals anything else ad hoc (`codesign --force --deep --sign -`),
  then verifies strictly and fails the job if the bundle still does not
  verify. A DMG the build already uploaded is kept as is: its producer (the
  product-name stage, decision 0210) seals it the same way.
- Left out: the Windows build script tests, the Linux slice check (its
  profile validator is not exported by Cosmyx builds, decision 0211), the
  universal macOS app and the Flatpak. Release validation covers them.

## Consequences

- An integration build costs only the OSes asked for, and behaves the same on
  every base.
- The `build_all.yml` hook of decision 0216 is no longer needed; removing it
  is done on that decision's branch.
- On v2.5.2, `build_check_cache.yml` looks for a base build of the calling
  workflow to wait for when a macOS deps cache misses; it finds none and
  builds the deps itself. On DEV it waits on `build_all.yml` as before.
- Workflows that watch `build_all.yml` runs (the macOS retry, decision 0217)
  must also watch "Cosmyx dev build".
- Removing this decision means deleting the workflow, `dev_build.py` and its
  test; integration builds then need another trigger.
