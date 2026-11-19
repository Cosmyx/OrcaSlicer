# GUI goldens recipes (T16). Imported by the root justfile.
# See wiki/cosmyx/gui-goldens.md.

# Capture the GUI of a finished "Build all" run in CI on every OS (MODE=update captures new goldens to fetch).
goldens-gui RUN_ID MODE="compare":
    gh workflow run cosmyx-gui-goldens.yml --repo {{repo}} -f run_id={{RUN_ID}} -f mode={{MODE}}

# Capture a "Build all" run twice in CI on every OS and check that both passes match.
goldens-gui-stability RUN_ID:
    gh workflow run cosmyx-gui-goldens.yml --repo {{repo}} -f run_id={{RUN_ID}} -f mode=compare -f stability=on

# Bring the failed, new and removed goldens of a CI goldens run into tests/cosmyx/gui/goldens (passed ones are kept).
goldens-gui-fetch RUN_ID:
    {{python}} scripts/cosmyx/gui_goldens/cli.py fetch --repo {{repo}} --run-id {{RUN_ID}}

# Write a before/after page of every golden changed in the working tree (build/cosmyx-gui-goldens/review).
goldens-gui-review:
    {{python}} scripts/cosmyx/gui_goldens/cli.py review --out build/cosmyx-gui-goldens/review

# Run the Linux pass of a "Build all" run here, in the pinned Docker image, and compare it with the goldens.
goldens-gui-local RUN_ID PASSES="1":
    {{python}} scripts/cosmyx/gui_goldens/cli.py local --repo {{repo}} --run-id {{RUN_ID}} --passes {{PASSES}}

# Show the latest GUI goldens runs.
goldens-gui-status:
    gh run list --repo {{repo}} --workflow cosmyx-gui-goldens.yml --limit 5
