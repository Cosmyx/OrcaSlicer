# Integration and rebase recipes (T20). Imported by the root justfile.

# Rebuild the integration branch of BASE (ci/cosmyx-integration for DEV, integration/<BASE> otherwise) with every PR branch; known conflicts auto-resolved. ARGS: --push (also cosmyx-ci/<BASE>) [--build: draft PR into cosmyx-ci/<BASE>].
cosmo-integrate BASE="origin/DEV" *ARGS:
    {{python}} scripts/cosmyx/integrate/cli.py integrate {{BASE}} --repo {{repo}} {{ARGS}}

# Dry run: replay every PR branch onto upstream TAG in a temporary worktree and print a conflict table; changes no branch.
cosmo-rebase-check TAG *ARGS:
    {{python}} scripts/cosmyx/integrate/cli.py rebase-check {{TAG}} {{ARGS}}
