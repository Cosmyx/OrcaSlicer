# Cosmyx recipes. Run `just` to list them. Every recipe works from macOS, Linux
# and Windows: each one is a single call to Python or gh, never a shell script.

set windows-shell := ["powershell.exe", "-NoLogo", "-NoProfile", "-Command"]

# Python launcher name: `python` on Windows, `python3` elsewhere.
python := if os_family() == "windows" { "python" } else { "python3" }

# GitHub repository the CI recipes act on.
repo := env("COSMYX_REPO", "Cosmyx/OrcaSlicer")

# Feature recipes, one file per task, loaded when present.
import? 'scripts/cosmyx/just/branding.just'
import? 'scripts/cosmyx/just/goldens.just'
import? 'scripts/cosmyx/just/i18n.just'
import? 'scripts/cosmyx/just/macos-signing.just'
import? 'scripts/cosmyx/just/signing.just'
import? 'scripts/cosmyx/just/sync.just'
import? 'scripts/cosmyx/just/tests.just'
import? 'scripts/cosmyx/just/version.just'

# List every recipe.
default:
    @just --list

# Run the tooling script tests (Python unittest, plus Pester when PowerShell is installed).
test-scripts:
    {{python}} scripts/cosmyx/run_script_tests.py

# Start the build_all workflow on a pushed branch (validation is CI only, no local deps build).
build-all BRANCH:
    gh workflow run build_all.yml --repo {{repo}} --ref {{BRANCH}}

# Show the latest build_all runs of a branch.
build-status BRANCH:
    gh run list --repo {{repo}} --workflow build_all.yml --branch {{BRANCH}} --limit 5

# List the decision register (wiki/decisions).
decisions:
    {{python}} scripts/cosmyx/decisions.py
