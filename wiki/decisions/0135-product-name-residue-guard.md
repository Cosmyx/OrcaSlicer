# 0135. No visible upstream name outside the allowlist

## Status

Accepted. Ports CosmoSlice D-005 and D-006. Amended: inflected names and
the inflection table; texts asserted by upstream tests are kept.

## Context

Upstream merges bring new texts that name OrcaSlicer. They must be caught
by the build rather than by a user, without breaking the automatic upstream
sync on every new string.

## Decision

- Guard G8 (the product-name plugin), before apply: every rename row still
  matches (its text in a literal or hint; a msgid row also in the template,
  its new msgid not there yet; a literal row not being a msgid), and every
  allowlist row still matches with its exact count. A stale row is an error
  on every build, except in the engine's tolerant mode (decision 0122: a
  tree whose upstream base is not DEV, such as an integration onto an older
  upstream tag), where a rename, allowlist or inflection row whose text the
  tree lacks entirely (old and new text absent from the sources, the hints
  and the template) is skipped with a warning. A row only partly there (a
  literal without its msgid) stays an error. The plugin reads the mode from
  the engine's context and is strict when the engine has none.
- After apply: each row is renamed in both places (old text gone, new text in
  the sources and, for a msgid row, in the template); no confirmed
  translation of a renamed msgid names the product (error); and no visible
  text names it outside the allowlist: non-log, non-include C++ literals under
  `src/` (Cosmyx files left out), template msgids still carried by a source,
  hints, and the translated elements of the setup-guide pages. That residue is
  drift: a warning on development builds, an error on release builds, like
  G3 and G4.
- An inflected name (decision 0134) left in a confirmed translation of a
  renamed msgid because `inflections.json` has no row for it is reported as
  "needs inflection row (<language>): <form>", at the drift level: a warning
  on development builds, so the upstream sync keeps building while a speaker
  writes the row, and an error on release builds. Before apply, an
  inflection row that renames no such translation in its language, applied
  as it is at apply time (whole words, after the longer rows of its
  language), is stale (error): a row always shadowed by a longer one is
  stale too. An invalid row is an error: `old` that does not name OrcaSlicer,
  is the bare plain name or has leading or trailing space; `new` without the
  CosmoSlice stem or still naming OrcaSlicer; a duplicate (language, old).
- Every input is read as UTF-8; a file that is not (hints, a guide page) is a
  clean G8 error, never a traceback.
- `allowlist.json` rows are `msgid`, `literal` (file, source text, exact
  count) or `text` (guide page), each with a reason starting with its
  category: `asset`, `cli`, `compared`, `credit`, `dev-tool`, `external`,
  `internal`, `kept-name`, `persisted`, `url`. 62 rows today: the About
  credits and copyright, the upstream releases named in messages, the CLI
  `result.json` texts, compared and persisted tags, client ids sent to
  third-party services, icon names, developer tools, and the plugin host's
  "OrcaSlicer application is not initialized" exception.
- A text that an upstream test under `tests/` asserts literally is never a
  rename target: renaming it breaks that test on every branded build, and
  the test is upstream's, so it cannot be changed without a conflict. Such a
  text is allowlisted instead (`compared`). The plugin host's exception
  texts are seen by plugins, not shown as interface text, so keeping them
  costs nothing visible. A script test fails when a rename row's old text
  appears in a non-Cosmyx `tests/**/*.cpp` file.

## Consequences

- A new upstream text naming OrcaSlicer shows up as a warning on the next
  MIXED or DEV build and blocks a release until a row covers it
  (`just brand-name-candidates` proposes one).
- Removing it: drop the plugin guards; renamed and new texts are no longer
  checked.
