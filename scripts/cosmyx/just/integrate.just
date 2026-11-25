# Integration and rebase recipes (T20). Imported by the root justfile.

# Rebuild the integration branch of BASE (ci/cosmyx-integration for DEV, integration/<BASE> otherwise) with every PR branch (replayed as rebase/<BASE>/* first on a non-DEV base); known conflicts auto-resolved. ARGS: --bundle N (only branches of bundle N or earlier), --push (also cosmyx-ci/<BASE>) [--build: draft PR into cosmyx-ci/<BASE>, built by Cosmyx dev build [--os linux,windows,macos-arm64,macos-x86_64: its build:* labels]]. Non-DEV base: --allow-whole-copy PATH, --drift-threshold N (40), --strict-drift.
cosmo-integrate BASE="origin/DEV" *ARGS:
    {{python}} scripts/cosmyx/integrate/cli.py integrate {{BASE}} --repo {{repo}} {{ARGS}}

# Dry run: replay every PR branch onto upstream TAG in a temporary worktree and print a conflict table; changes no branch. ARGS: --bundle N.
cosmo-rebase-check TAG *ARGS:
    {{python}} scripts/cosmyx/integrate/cli.py rebase-check {{TAG}} {{ARGS}}
