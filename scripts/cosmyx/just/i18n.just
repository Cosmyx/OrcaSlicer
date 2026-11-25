# Translation recipes (T8). Imported by the root justfile.

# Image the Docker extraction runs in (Python plus GNU gettext from Debian).
i18n_image := "python:3.12-slim-bookworm"

# Refresh localization/cosmyx (templates and every <lang>.po) from src/**/Cosmyx/** (needs xgettext; see i18n-extract-docker).
i18n-extract:
    {{python}} scripts/cosmyx/i18n_extract.py extract

# Same as i18n-extract, inside Docker, for machines without GNU gettext.
i18n-extract-docker:
    docker run --rm -v "{{justfile_directory()}}:/repo" -w /repo {{i18n_image}} sh -c "apt-get update -qq && apt-get install -y -qq gettext >/dev/null && python scripts/cosmyx/i18n_extract.py extract"

# List the Cosmyx translations still missing, per feature and language (ARGS: --lang LANG, --strict to exit 1 on a gap).
i18n-coverage *ARGS:
    {{python}} scripts/cosmyx/i18n_coverage.py {{ARGS}}

# Fill empty Cosmyx translations from the OrcaSlicer catalogues of a git ref (for example the old Cosmyx branch).
i18n-seed REF:
    {{python}} scripts/cosmyx/i18n_extract.py seed --ref {{REF}}

# Check the graft of localization/cosmyx into localization/i18n and print the counts, writing nothing.
i18n-graft-dry-run:
    {{python}} scripts/cosmyx/i18n_graft.py --dry-run

# Graft localization/cosmyx into localization/i18n in place, as the CI does before a build (undo with i18n-ungraft).
i18n-graft:
    {{python}} scripts/cosmyx/i18n_graft.py

# Restore the committed localization/i18n after a graft, also clearing the skip-worktree bit the CI's hide step sets.
i18n-ungraft:
    {{python}} scripts/cosmyx/worktree_clean.py unhide localization/i18n
    git checkout -- localization/i18n

# List the tracked files hidden from git diff by skip-worktree (set by the CI's prepare step).
worktree-hidden:
    {{python}} scripts/cosmyx/worktree_clean.py show
