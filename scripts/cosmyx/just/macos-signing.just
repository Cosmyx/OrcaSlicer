# macOS signing recipes (T15). See wiki/cosmyx/macos-signing.md.

# Sign a copy of a local macOS APP ad-hoc in the CI's order and verify it (macOS only: needs codesign).
mac-sign-dryrun APP:
    {{python}} scripts/cosmyx/macos_signing/cli.py dryrun {{APP}}

# Show the macOS signing step of the latest "Build all" runs of BRANCH (needs gh).
mac-sign-status BRANCH="DEV":
    {{python}} scripts/cosmyx/macos_signing/cli.py status --repo {{repo}} --branch {{BRANCH}}
