# 0088. UTF-8 catalogues only

## Status

Accepted.

## Context

The graft writes the Cosmyx entries as UTF-8 text into the OrcaSlicer
catalogue and keeps that catalogue's header as it is. If the header declared
another charset (ISO-8859-1, for example), msgfmt would read the grafted UTF-8
bytes in that charset and garble every non-ASCII translation without any
error. A Cosmyx catalogue saved in another encoding cannot even be decoded as
UTF-8. Every OrcaSlicer and Cosmyx catalogue is UTF-8 today.

## Decision

- The graft refuses, with an error naming the file, any OrcaSlicer or Cosmyx
  catalogue whose header declares a charset other than UTF-8, and any
  catalogue whose bytes are not valid UTF-8. It does not convert: a
  conversion would rewrite every upstream entry and hide a real problem.
- A header without a charset is read as UTF-8. Templates (`messages.pot`,
  `charset=CHARSET`) are not grafted and are not checked.
- The PO reader splits lines on LF only (after turning CRLF into LF), so a
  string holding U+2028, U+2029, U+0085, a form feed or an ASCII separator
  stays one string, as for gettext. An unescaped quote inside a string is an
  error, as for msgfmt.

## Consequences

- An upstream switch to another charset stops the build with a clear message
  instead of shipping garbled translations. The fix is `msgconv
  --to-code=UTF-8` on that catalogue.
- Removing it: drop `require_utf8()` from `scripts/cosmyx/i18n_graft.py`, or
  replace it with a conversion of the grafted entries to the declared charset.
