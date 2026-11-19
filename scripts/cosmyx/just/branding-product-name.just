# Product-name recipes (T11e). Imported by branding.just. Tables: cosmyx-src/branding/product-name/.

# Propose product-name rows (rename, literals, stale) for what upstream added since the tables were written; writes nothing.
brand-name-candidates:
    {{python}} scripts/cosmyx/branding/product_name/candidates.py

# List the inflected product names (per language, with an example) that still need an inflection row; writes nothing unless OUT is given.
brand-name-inflections OUT="":
    {{python}} scripts/cosmyx/branding/product_name/inflections.py {{ if OUT == "" { "" } else { "--out " + OUT } }}
