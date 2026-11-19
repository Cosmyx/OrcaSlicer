# 0148. Shipped content: names, translations and models

## Status

Accepted.

## Context

The Cosmyx tasks change what ships: the build tag in every name (T6), the
grafted translations (T8) and the Cosmyx models (T5). A build step could drop
any of them silently.

## Decision

- Names: every `OrcaSlicer_*` artifact except the `Mac_bundle` tarballs
  carries `<display version>_<hash>`, the hash a prefix of the built commit (7
  characters or more). The display version comes from the trusted
  `cosmyx_version.py` applied to the built commit's files.
- Translations: every translated, non-fuzzy entry of
  `localization/cosmyx/<feature>/<lang>.po` reads the same from the shipped
  `i18n/<lang>/OrcaSlicer.mo` (`gettext`, contexts, plurals for n=1). The `.po`
  files are parsed with `parse_po` of the trusted `i18n_graft.py`. A missing
  catalogue fails; a language OrcaSlicer does not ship is a warning.
- Models: every file of `resources/cosmyx/` of the built commit is shipped with
  the same SHA-256.
- The shipped resources folder is the one holding `i18n/` and `profiles/`.
- A part whose sources are not in the built commit yet is skipped and names
  the task that brings it.

## Consequences

- The branding guard (T11) is deferred; if T11 renames the artifacts, the
  patterns in `data/expectations.json` change with it.
- Removing it: drop `content.py` and the names check in `inventory.py`.
