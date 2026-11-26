# SVG recolour candidates (T11d). Imported by branding.just. Tool: scripts/cosmyx/branding/candidates.py.

# Write recoloured SVG candidates (validated colour mappings only) under build/cosmyx/candidates; commits nothing.
brand-candidates:
    {{python}} scripts/cosmyx/branding/candidates.py generate

# Write the HTML review sheets of the candidates (before/after, light and simulated dark) under build/cosmyx/review.
brand-review:
    {{python}} scripts/cosmyx/branding/candidates.py review

# Copy the reviewed candidates matching a group or glob into the overlay as to-validate rows, e.g. `just brand-accept icons-a-m`.
brand-accept GLOB:
    {{python}} scripts/cosmyx/branding/candidates.py accept {{quote(GLOB)}}
