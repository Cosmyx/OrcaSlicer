# 0179. Goldens harness input validation

## Status

Accepted.

## Context

The goldens harness (`scripts/cosmyx/gui_goldens/`) reads two kinds of input
it does not control: the events the in-app driver writes to `events.jsonl`
(decision 0164) and PNG files, from `screencapture` on macOS and from the
committed goldens (decision 0171). The breaker round found that:

- a surface id was joined to the images folder as it came, so `../x` wrote
  outside it, and `CON`, `a:b` or an empty id could not be written on Windows;
- a second capture with the same id silently overwrote the first;
- an event of the wrong JSON shape (`[]`, masks given as an object,
  `"seq": true`) escaped as a raw Python exception instead of a failed pass;
- the PNG decoder never checked chunk CRCs, and a truncated or inconsistent
  file escaped as `zlib.error`, `IndexError` or `struct.error`.

## Decision

- A surface id must match `[0-9]{2}-[a-z0-9]+(-[a-z0-9]+)*` (ASCII), the
  pattern `is_valid_surface_id()` already enforces on the script in
  `logic/GoldenScript.cpp`; the `surfaces` text event is the one fixed name
  outside it. Such names are portable on every OS: no separator, no reserved
  Windows name, no forbidden character. `protocol.image_file_name()` and
  `text_file_name()` check the id themselves, so no caller can bypass it.
- A file name written twice in one pass is a failure of that surface; the
  first file is kept.
- `protocol.validate()` checks the shape: the event is an object, `seq` is an
  integer and not a boolean, rectangles are lists of four integers, `masks`
  and `webviews` are lists, `scale` is a number, text content and fail fields
  are strings. Any mismatch is a `GoldenError`.
- `png.decode()` checks every chunk's length and CRC, requires `IEND`, a
  13-byte `IHDR`, a `PLTE` for palette images and palette indices inside it,
  and exactly the pixel bytes `IHDR` implies. It never inflates past that
  size, and refuses images over 64 Mpx (`MAX_PIXELS`, 256 MiB of RGBA), far
  above any real capture, so a damaged or hostile `IHDR` cannot ask for
  gigabytes. Every problem is a `GoldenError`.

## Consequences

- A PNG without `IEND`, or with a bad CRC, that used to decode is now
  rejected; the files the harness and `screencapture` write are valid.
- A capture larger than 64 Mpx (for example a full 8K screen at scale 2)
  would need `MAX_PIXELS` raised.
- Removing it: drop the checks in `protocol.py`, `png.py` and `Pass.claim()`
  in `cli.py`, and accept files written outside the images folder, silent
  overwrites and raw exceptions on damaged input.
