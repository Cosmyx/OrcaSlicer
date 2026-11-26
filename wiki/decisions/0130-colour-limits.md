# 0130. Known limits of the colour stage

## Status

Accepted.

## Context

Dark mode is forced for everyone (decision 0139), so the colours must read on
the dark screen first. Some surfaces cannot be fixed by the colour stage.

## Decision

- Contrast (WCAG 2) of every mapping on `#FFFFFF` and `#1C1C1F` is reported
  by `just brand-colour-candidates`, in the build report and in
  `wiki/cosmyx/branding.md`; it informs the review and never fails a build.
- Accepted for now: white text on `#A472F5` is 3.33:1 (large text only);
  `#8000FF` on the dark background is 2.72:1 where a colour reaches the
  screen without the dark map (dark hover, links in HTML dialogs). Each is
  one `to` edit away if the user prefers `#A472F5`.
- Icons loaded by OpenGL or ImGui (`GLTexture`, `ImGuiWrapper`,
  `IconManager`) keep the colour of their SVG on disk; they turn violet when
  the SVG itself is replaced (task T11d).
- The derived dark tint 10 is `#393444`; the exact blend is `#393445`.

## Consequences

- Until the SVG candidates land, the 3D toolbar and gizmo icons stay teal.
- Revisiting a limit is a new decision that supersedes this one.
