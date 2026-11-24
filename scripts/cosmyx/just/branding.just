# Branding recipes (T11). Imported by the root justfile. Tables: cosmyx-src/branding/.

# Run the branding guards on the tree and check the review tables, writing nothing (MODE: strict or tolerant).
brand-check MODE="":
    {{python}} scripts/cosmyx/branding/cli.py check {{ if MODE == "" { "" } else { "--mode " + quote(MODE) } }}

# Brand the local tree as the CI does; MODE=tolerant skips rows an older upstream base lacks. Undo with brand-revert.
brand-apply MODE="":
    {{python}} scripts/cosmyx/branding/cli.py apply {{ if MODE == "" { "" } else { "--mode " + quote(MODE) } }}

# Print the branding mode this environment selects (strict unless the upstream base is not DEV).
brand-mode:
    {{python}} scripts/cosmyx/branding/cli.py mode

# Restore every file the last brand-apply wrote, byte for byte.
brand-revert:
    {{python}} scripts/cosmyx/branding/cli.py revert

# Bring the manifest and the review tables in line with the tree (new teal icons, new overlay files, upstream hashes).
brand-sync:
    {{python}} scripts/cosmyx/branding/cli.py sync

# Re-baseline rows after an upstream or overlay change (a group name or a path glob); rows with an overlay go back to to-validate.
brand-refresh PATH:
    {{python}} scripts/cosmyx/branding/cli.py refresh {{quote(PATH)}}

# USER ONLY, never agents: mark to-validate rows validated, e.g. `just brand-validate logos --i-am-the-user`.
brand-validate GLOB *FLAGS:
    {{python}} scripts/cosmyx/branding/cli.py validate {{quote(GLOB)}} {{FLAGS}}

# Regenerate the review tables under wiki/cosmyx/branding-assets from the manifest.
brand-table:
    {{python}} scripts/cosmyx/branding/cli.py render

# Each branding sub-task keeps its recipes in its own file, loaded when present,
# so the sub-task branches never edit this file (decision 0120).
import? 'branding-logos.just'
import? 'branding-colours.just'
import? 'branding-candidates.just'
import? 'branding-product-name.just'
