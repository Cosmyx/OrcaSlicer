# 0164. Protocol v1 between the driver and the harness

## Status

Accepted.

## Context

The driver cannot capture the screen itself (window decorations, native menus
and system WebViews are outside its reach), so it needs to hand each capture
to the harness and wait for it, without blocking its own event loop.

## Decision

- The driver appends one JSON object per line to `<dir>/events.jsonl`:
  `hello` (protocol, version, `GL_RENDERER`, `GL_VERSION`, display, scale, OS),
  `capture` (id, kind main, dialog, menu or menubar, `rect_px`, scale, script
  masks, WebView rectangles, title, menu label), `text` (id, content), `fail`
  (id, reason) and `done` (error count). Every event has an increasing `seq`.
- After a capture, the driver polls for `<dir>/ack-<seq>`, which the harness
  writes with an atomic rename once the screen is captured and a menu closed.
- Rectangles are in screen pixels: wxWidgets coordinates times
  `GetContentScaleFactor()` (1 on Windows, where coordinates are already
  pixels).
- Limits: 30 s per step in the driver, 40 s of silence and 40 minutes per pass
  in the harness. A step that fails is reported and skipped; the pass goes on.

## Consequences

- Files only: no socket, no extra dependency, the same on every OS.
- A version change of the protocol changes `protocol_version` in
  `GoldenScript.hpp` and `PROTOCOL` in `protocol.py` together.
