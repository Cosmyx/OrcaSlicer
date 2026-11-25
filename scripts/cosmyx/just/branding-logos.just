# Logo recipes (T11b). Imported by branding.just. Sources: cosmyx-src/branding/overlay/.

# Render the derived logos (ICO, ICNS, MSIX and other PNGs) from the vendored SVG master in the pinned resvg image.
brand-derive:
    {{python}} scripts/cosmyx/branding/derive/derive.py write --docker

# Fail when a committed derived logo differs from a fresh render in the pinned resvg image.
brand-derive-check:
    {{python}} scripts/cosmyx/branding/derive/derive.py check --docker

# Render every derived logo twice in the pinned resvg image and fail if the two runs differ.
brand-derive-stable:
    {{python}} scripts/cosmyx/branding/derive/derive.py stable --docker
