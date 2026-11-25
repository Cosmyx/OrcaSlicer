# 0121. Branding rows need the user's validation before a release

## Status

Accepted.

## Context

Every vendored image or colour must be approved by the user, who owns the
brand. Development builds still need to run while replacements are being
added, and agents produce most of the candidates.

## Decision

- A manifest row is `missing` (no overlay file, no recorded override hash),
  `to-validate` (an overlay is recorded but not approved) or `validated`.
- Development builds (pull requests whatever their target, `DEV`, `MIXED`,
  any other branch, local runs) apply every recorded overlay and warn, one
  line per group and status, about `missing` and `to-validate` rows. Release
  builds (`refs/heads/release/*` and tags) fail on them. `COSMYX_BRAND_REF`
  overrides the GitHub ref for local runs and tests.
- Only the user moves a row to `validated`, with
  `just brand-validate <group or glob> --i-am-the-user`. The command refuses
  without the flag (or `COSMYX_BRAND_VALIDATOR` set), outside an interactive
  terminal, in CI (`CI` or `GITHUB_ACTIONS` set), and without the typed
  confirmation `validate`. Agents never run it. It also refuses an overlay
  whose hash differs from the recorded one.
- Any later change to an approved row (`just brand-refresh`) sends it back to
  `to-validate`.

## Consequences

- A release cannot ship an image the user has not seen.
- Today every row is `missing`, so release builds fail until the logos and
  icons are vendored and validated.
- Removing it: drop the status policy in `guards.py` and the `validate`
  command; release builds then ship unreviewed replacements.
