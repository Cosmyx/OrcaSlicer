# 0169. System WebViews are masked on Windows and macOS

## Status

Accepted.

## Context

Home, Project, the setup guide and several dialogs are WebViews. On Windows
(WebView2) and macOS (WKWebView) the engine updates with the OS; on Linux the
pinned WebKitGTK renders the same pixels every time.

## Decision

- The driver reports every WebView rectangle of a capture. On Windows and
  macOS (`webview_mask` in `tolerance.json`) the harness paints them #FF00FF
  before storing the image; on Linux they stay in the image.
- The text of each WebView (`document.body.innerText`, read with
  `RunScriptAsync`) is a text golden, `<id>-webview.txt`, on every OS.
- Masks listed in the script are always painted.

## Consequences

- WebView layout changes on Windows and macOS are caught by text, not pixels.
