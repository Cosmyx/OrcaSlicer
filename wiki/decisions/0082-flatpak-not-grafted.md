# 0082. The Flatpak build is not grafted

## Status

Accepted.

## Context

The Flatpak bundle is built by `build_flatpak.yml` (called from
`build_all.yml`) through flatpak-builder, which compiles the catalogues inside
its own sandbox from the checked-out tree. It does not go through
`build_orca.yml`, where the graft hook lives (decision 0080).

## Decision

The Flatpak build is not grafted for now: it ships the Cosmyx features with
English labels for the Cosmyx strings. Adding a second hook in
`build_flatpak.yml` would be one more upstream edit for a package Cosmyx does
not distribute today.

## Consequences

- The Linux AppImage, macOS and Windows builds are translated; the Flatpak one
  is not, for Cosmyx strings only.
- Closing the gap: call `.github/actions/cosmyx-i18n-graft` in
  `build_flatpak.yml` after its checkout, with a `# Cosmyx` hook line.
