# GUI goldens

Every screen of the built application is pinned to a committed image, on
Linux, macOS and Windows. A workflow starts the build a "Build all" run
produced, walks it through every surface, captures each one and compares it
with `tests/cosmyx/gui/goldens/<os>/`. Decisions 0162 to 0179.

## How it works

```text
harness (scripts/cosmyx/gui_goldens)            application (GoldenDriver)
  seed the data folder, start the build  --->   COSMYX_GUI_DRIVER_DIR set: driver starts
                                         <---   hello, surfaces.txt
                                         <---   capture {id, kind, rect_px, masks, webviews}
  capture the screen, mask, store PNG
  write ack-<seq>                        --->   close the dialog or menu, next step
                                         <---   text, fail ...
                                         <---   done {errors}
  stop the app, check the G-code, compare
```

- The driver (`src/slic3r/GUI/Cosmyx/GoldenDriver.cpp`) is inert unless
  `COSMYX_GUI_DRIVER_DIR` is set. It reads `tests/cosmyx/gui/script.json`
  (or `COSMYX_GUI_DRIVER_SCRIPT`), runs each step from a 50 ms timer, opens
  modal dialogs and menus through `CallAfter` and closes them once captured.
  Two hook lines in `GUI_App.cpp` start it (decision 0163).
- The protocol is files only: `events.jsonl` and `ack-<seq>` (decision 0164).
  The harness checks the shape of every event, accepts only surface ids that
  are portable file names, reports a surface written twice in a pass, and
  decodes PNG files strictly (chunk CRCs, sizes, at most 64 Mpx); anything
  else is a failed surface, never a crash (decision 0179).
- Captures are native: `xwd` under Xvfb on Linux, `screencapture` on macOS,
  `BitBlt` on Windows (decision 0165).

## The script

`tests/cosmyx/gui/script.json` lists literal steps and generators:

| Section | Surfaces |
|---------|----------|
| 00 | start screen |
| 10 | main tabs: Home, Project, Calibration, Design, Preview, Prepare |
| 20 | every menu (top bar popups on Windows and Linux, menu bar on macOS) and `20-menu-tree.txt` |
| 30 | catalog commands that open a dialog on an empty plate |
| 40 | the six Preferences tabs |
| 50 | the loaded cube and every visible settings page |
| 60 | the first screen of each calibration |
| 70 | selection, context menu, view and object commands |
| 90 | the UI slice: Preview, the layer slider, the G-code |
| 99 | catalog commands skipped with no section |

Each step: `id`, `do` (actions: `tab`, `command`, `prefs_tab`, `settings`,
`load`, `reset`, `select_all`, `context_menu`, `menu`, `wait`, `slice`,
`copy_gcode`, `close_tips`), `capture` (`main`, `dialog`, `auto`, `menu`,
`menubar`, `none`), `close`, `mask`, `assert` (`canvas_ready`,
`slice_valid`), `os`, `skip`, `settle_ms`, `after`.

`menu_items` classifies every `NativeCommands::catalog()` key (decision
0173): `dialog`, `view`, `toggle`, `any` or `skip` with a reason. A new
upstream command fails the goldens and the script tests until it gets a rule.
`exclude` lists what the first set leaves out (decision 0178).

## Comparison

- Linux: byte-exact, in the pinned image `tests/cosmyx/gui/docker/Dockerfile`
  (decision 0166).
- Windows and macOS: `tests/cosmyx/gui/tolerance.json` (decision 0168);
  WebViews masked #FF00FF, their text kept as `<id>-webview.txt`
  (decision 0169).
- Text goldens are byte-exact everywhere; `environment.json` only reports
  drift (renderer, display, platform).
- The UI slice G-code is checked with the T13 rules (`slice.py`).
- A second pass checks stability when the goldens tooling changed, in update
  mode and weekly (decision 0175).

## Recipes

The recipes live in `scripts/cosmyx/just/goldens.just`.

| Recipe | What it does |
|--------|--------------|
| `just goldens-gui RUN_ID [MODE]` | capture a Build all run in CI (`update` captures new goldens) |
| `just goldens-gui-stability RUN_ID` | capture twice in CI and compare the passes |
| `just goldens-gui-fetch RUN_ID` | bring the failed, new and removed goldens of a CI run into the tree |
| `just goldens-gui-review` | before/after page of every changed golden |
| `just goldens-gui-local RUN_ID [PASSES]` | Linux pass here, in the pinned image |
| `just goldens-gui-status` | latest runs |
| `just test-scripts` | the harness tests (fake driver, fake tools, one real capture per OS when allowed) |

## Refreshing the goldens

1. Push the branch and run Build all on it (`just build-all BRANCH`).
2. `just goldens-gui <run id> update`, wait for it to finish.
3. `just goldens-gui-fetch <goldens run id>`: only failed, new and removed
   goldens change.
4. `just goldens-gui-review` and look at every image. A change you did not
   intend is a regression: fix the code, not the golden.
5. Commit the goldens with the code change, and put the before/after view in
   the pull request.

## Status

The workflow posts `cosmyx/gui-goldens` on the built commit of every compare
run: success only when every OS matched. It fails when the build failed, came
from a fork (never run), lacked an OS artifact, had no committed goldens yet,
or did not match. `MIXED` only reports. Requiring it on DEV and release/* is a
branch protection setting (decision 0177).
