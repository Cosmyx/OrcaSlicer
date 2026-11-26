# 0163. The goldens driver starts only when asked

## Status

Accepted.

## Context

The driver ships inside every build, so it must cost nothing when nobody uses
it, and it must reach upstream code through the smallest possible hook.

## Decision

- `Cosmyx::start_golden_driver_if_requested()` does nothing unless the
  environment variable `COSMYX_GUI_DRIVER_DIR` names a folder. It starts the
  driver at most once (a static flag), because `post_init()` can run again on
  Linux.
- Two hook lines in `src/slic3r/GUI/GUI_App.cpp`, both tagged `// Cosmyx`: the
  include after the last Cosmyx include, and the call right after
  `this->post_init();` in the idle handler of `on_init_inner()` (a part of the
  file that has been calm since 2024).
- The driver object is never deleted: it lives until the harness kills the
  process, and destroying its timer after wxWidgets shut down would crash the
  exit.

## Consequences

- A normal start reads one environment variable and nothing else.
- Removing it: drop the two hook lines; nothing else in upstream code refers
  to the driver.
