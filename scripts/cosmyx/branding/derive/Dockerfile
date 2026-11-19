# Pinned image the branding derivation renders in (scripts/cosmyx/branding/derive, decision 0124).
# Built and run as linux/amd64 by derive.py --docker, so every host gets the same bytes.
# It needs no build context: derive.py pipes this file to `docker build -`.

# resvg rasterises the SVG masters. Pinned by crate version and its own Cargo.lock (--locked), built in a
# digest-pinned Rust image; only the binary reaches the final stage.
FROM rust:1.90-slim-bookworm@sha256:64232e656c058f4468e8d024e990acff04f0fd5a5c0a88a574dc37773d7325c9 AS resvg
RUN cargo install resvg --version 0.48.1 --locked --root /opt/resvg

FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337 AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8

COPY --from=resvg /opt/resvg/bin/resvg /usr/local/bin/resvg
