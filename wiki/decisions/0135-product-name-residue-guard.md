# 0135. No visible upstream name outside the allowlist

## Status

Accepted. Ports CosmoSlice D-005 and D-006.

## Context

Upstream merges bring new texts that name OrcaSlicer. They must be caught
by the build rather than by a user, without breaking the automatic upstream
sync on every new string.

## Decision

- Guard G8 (the product-name plugin), before apply: every rename row still
  matches (its text in a literal or hint; a msgid row also in the template,
  its new msgid not there yet; a literal row not being a msgid), and every
  allowlist row still matches with its exact count. A stale row is an error
  on every build.
- After apply: each row is renamed in both places (old text gone, new text in
  the sources and, for a msgid row, in the template); no confirmed
  translation of a renamed msgid names the product (error); and no visible
  text names it outside the allowlist: non-log, non-include C++ literals under
  `src/` (Cosmyx files left out), template msgids still carried by a source,
  hints, and the translated elements of the setup-guide pages. That residue is
  drift: a warning on development builds, an error on release builds, like
  G3 and G4.
- `allowlist.json` rows are `msgid`, `literal` (file, source text, exact
  count) or `text` (guide page), each with a reason starting with its
  category: `asset`, `cli`, `compared`, `credit`, `dev-tool`, `external`,
  `internal`, `kept-name`, `persisted`, `url`. 60 rows today: the About
  credits and copyright, the upstream releases named in messages, the CLI
  `result.json` texts, compared and persisted tags, client ids sent to
  third-party services, icon names, developer tools.

## Consequences

- A new upstream text naming OrcaSlicer shows up as a warning on the next
  MIXED or DEV build and blocks a release until a row covers it
  (`just brand-name-candidates` proposes one).
- Removing it: drop the plugin guards; renamed and new texts are no longer
  checked.
