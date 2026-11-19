# Upstream sync recipes (T10). Imported by the root justfile.

# Rebuild MIXED (DEV + Orca-Upstream) in a scratch repository and push nothing.
sync-mixed-dry-run:
    {{python}} scripts/cosmyx/upstream_sync.py mixed --dry-run --origin https://github.com/{{repo}}.git

# Check that every scheduled workflow is allowed or disabled by the policy.
workflow-policy:
    {{python}} scripts/cosmyx/upstream_sync.py workflow-policy

# Disable on GitHub the workflows the policy lists (needs gh auth with actions write).
workflow-policy-apply:
    {{python}} scripts/cosmyx/upstream_sync.py workflow-policy --apply --repo {{repo}}

# Start the upstream sync workflow on DEV (dry run by default: pushes nothing).
sync-dispatch DRY_RUN="true":
    gh workflow run cosmyx-upstream-sync.yml --repo {{repo}} --ref DEV -f dry_run={{DRY_RUN}}
