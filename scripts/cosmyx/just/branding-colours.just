# Colour recipes (T11c). Imported by branding.just. Table: cosmyx-src/branding/colours.json.

# Print the colour mappings with their WCAG contrast on #FFFFFF and #1C1C1F, and the candidate blends; writes nothing.
brand-colour-candidates:
    {{python}} scripts/cosmyx/branding/colours.py candidates

# Regenerate the tuple literal rows of colours.json from the tree (after an upstream change); hand-written rows are kept.
brand-colour-literals:
    {{python}} scripts/cosmyx/branding/colours.py literals --write
