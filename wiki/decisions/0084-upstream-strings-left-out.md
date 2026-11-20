# 0084. Strings OrcaSlicer already has stay out of the Cosmyx templates

## Status

Accepted.

## Context

Cosmyx code reuses strings OrcaSlicer already translates, such as the `℃`
side text of the ironing temperature option. Listing them in the Cosmyx
templates would ask every language agent to translate them again, and an
untranslated Cosmyx copy never wins over the OrcaSlicer translation anyway.

## Decision

`i18n_extract.py extract` drops from each template every (msgctxt, msgid) found
in `localization/i18n/OrcaSlicer.pot`.

## Consequences

- Translators only see strings OrcaSlicer does not have.
- If upstream later drops one of those strings, the next `just i18n-extract`
  puts it back into the Cosmyx template, untranslated.
- Overriding an OrcaSlicer translation on purpose stays possible through the
  graft rules, but is not part of the extraction.
- Removing it: delete `filter_template()` and its call.
