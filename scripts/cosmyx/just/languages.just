# UI language recipes (T25, decision 0220). Imported by the root justfile.

# Print the offered UI languages (src/slic3r/GUI/Cosmyx/logic/UiLocaleTable.inc).
languages:
    {{python}} scripts/cosmyx/languages.py table

# Create or refresh the Cosmyx language catalogues (localization/cosmyx/i18n) from OrcaSlicer.pot.
languages-generate:
    {{python}} scripts/cosmyx/languages.py generate

# Give every feature catalogue folder of localization/cosmyx a <lang>.po for every language.
languages-sync-features:
    {{python}} scripts/cosmyx/languages.py sync-features

# Check the language table and the Cosmyx language catalogues.
languages-check:
    {{python}} scripts/cosmyx/languages.py check

# Copy the Cosmyx language catalogues into localization/i18n, as the CI does before a build (undo with languages-uninstall).
languages-install:
    {{python}} scripts/cosmyx/languages.py install

# Remove the catalogues languages-install copied into localization/i18n.
languages-uninstall:
    {{python}} scripts/cosmyx/languages.py uninstall

# Compile every Cosmyx language catalogue with msgfmt --check-format --check-header, inside Docker.
languages-msgfmt-docker:
    docker run --rm -v "{{justfile_directory()}}:/repo:ro" -w /repo -e PYTHONDONTWRITEBYTECODE=1 -e COSMYX_REQUIRE_MSGFMT=1 {{i18n_image}} sh -c "apt-get update -qq && apt-get install -y -qq gettext >/dev/null && python -m unittest discover -s scripts/cosmyx/tests -p test_languages.py -t scripts/cosmyx/tests"
