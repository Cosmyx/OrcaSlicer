# 0080. Graft the Cosmyx translations at build time

## Status

Accepted.

## Context

OrcaSlicer loads a single gettext catalogue per language, compiled from
`localization/i18n/<lang>/OrcaSlicer_<lang>.po`. Upstream regenerates those
files often, so Cosmyx strings committed into them would conflict with almost
every upstream merge, which the zero-conflict rule forbids. Loading a second
catalogue at runtime would need a GUI hook in `GUI_App.cpp`, one of the most
edited upstream files.

## Decision

- The Cosmyx strings live outside `localization/i18n` (decision 0081).
- In CI, `scripts/cosmyx/i18n_graft.py` merges them into the OrcaSlicer
  catalogues in place, before the build compiles the `.mo` files. Rules: key
  (msgctxt, msgid); a translated, non-fuzzy Cosmyx entry replaces the
  OrcaSlicer one and is not fuzzy; fuzzy or empty Cosmyx entries never win;
  Cosmyx-only keys are appended; obsolete entries are dropped; plurals are
  kept; the OrcaSlicer header is kept; the same key in two features is an
  error; a language OrcaSlicer lacks is a warning. Every check runs before a
  file is written.
- The graft runs from the composite action `.github/actions/cosmyx-prepare`
  (graft unit tests, then the graft, then the edited files are hidden from git
  diff, decision 0087), called by one upstream hook in
  `.github/workflows/build_orca.yml` right after Checkout, skipped on the macOS
  combine-only leg, which compiles nothing. The Flatpak build calls it too
  (decision 0086).
- Locally the graft is never committed: `just i18n-graft` grafts for a local
  check and `just i18n-ungraft` restores the committed files.

## Consequences

- One three-line hook in `build_orca.yml`, placed after Checkout where upstream
  rarely edits.
- A broken Cosmyx catalogue fails every build leg at the graft step, before the
  long compile.
- Removing it: delete the hook, the action, the script and
  `localization/cosmyx`; the build then ships the OrcaSlicer catalogues only.
