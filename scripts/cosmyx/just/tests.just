# Artifact check recipes (T13). Imported by the root justfile.
# See wiki/cosmyx/artifact-checks.md.

# Start the artifact checks on a finished "Build all" run in CI (STRICT=true fails on any skipped check).
artifact-checks RUN_ID STRICT="false":
    gh workflow run cosmyx-artifact-checks.yml --repo {{repo}} -f run_id={{RUN_ID}} -f strict={{STRICT}}

# Show the latest artifact check runs.
artifact-checks-status:
    gh run list --repo {{repo}} --workflow cosmyx-artifact-checks.yml --limit 5

# Download a "Build all" run's artifacts for this OS into build/cosmyx/artifacts/RUN_ID and check them here (read-only).
artifact-checks-local RUN_ID:
    {{python}} scripts/cosmyx/artifact_checks/cli.py local --repo {{repo}} --run-id {{RUN_ID}}
