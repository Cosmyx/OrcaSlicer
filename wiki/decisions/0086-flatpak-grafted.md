# 0086. The Flatpak build is grafted

## Status

Accepted. Supersedes 0082.

## Context

Decision 0082 left the Flatpak bundle untranslated for the Cosmyx strings, to
save one upstream edit. The Cosmyx build-time edits now go beyond the
translations (the branding of T11 runs from the same action), so a Flatpak
build without them would ship the OrcaSlicer branding and English Cosmyx
labels. flatpak-builder copies `localization/`, `resources/` and `src/` from
the working tree (`type: dir` sources in
`scripts/flatpak/com.orcaslicer.OrcaSlicer.yml`), so an edit made in the tree
after checkout reaches the sandbox. The skip-worktree bit (decision 0087) only
changes what git reports; the files on disk, which flatpak-builder copies, keep
the edits.

## Decision

`build_flatpak.yml` calls `.github/actions/cosmyx-prepare` in one two-line
hook (`# Cosmyx` tags) right after its `actions/checkout` step, before the
version step and the flatpak-builder run.

The Flatpak job runs in a Fedora container, where `actions/setup-python`
(Ubuntu builds only) is not reliable, so the action uses the container's own
`python3` (3.9 or newer) when it runs inside a job container, and falls back to
`actions/setup-python` otherwise.

## Consequences

- Every desktop build, Flatpak included, carries the same Cosmyx catalogues.
- One more upstream hook, placed after a checkout line upstream rarely edits.
- Removing it: delete the two hook lines in `build_flatpak.yml`; the Flatpak
  bundle then ships the plain OrcaSlicer catalogues and branding again.
