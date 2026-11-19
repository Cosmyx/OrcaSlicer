# 0126. Logos render in a pinned resvg image

## Status

Accepted.

## Context

A derived raster is committed and compared byte for byte with a fresh
render, so the renderer and its platform must be the same on every machine.
Host renderers differ by version, fonts and CPU.

## Decision

- `scripts/cosmyx/branding/derive/Dockerfile` is the only renderer: resvg
  0.48.1 built with `cargo install --locked` in a digest-pinned Rust image,
  copied into a digest-pinned `python:3.12-slim-bookworm` image (the same pins
  as CosmoSlice's CI image). It needs no build context.
- `derive.py --docker` builds the image when its tag (a hash of the
  Dockerfile) is absent, and runs the script inside it as linux/amd64 with the
  tree mounted, as the host user. The recipes always use it.
- The test `test_branding_logos.py` compares every derived output with a fresh
  render in that image. It skips, with the reason in its message, where the
  image cannot run (no Docker, no daemon, Windows containers, or a non-amd64
  daemon without linux/amd64 emulation, found by starting the digest-pinned
  final-stage base image once), as on the macOS and Windows runners of
  `cosmyx-checks.yml`; the Linux runner runs it. It also skips in the
  cosmyx-prepare action of a build leg (`COSMYX_TEST_PROFILE=prepare`,
  decision 0120), so no build leg compiles resvg.

## Consequences

- The first run on a machine builds resvg (several minutes under emulation on
  arm64); later runs reuse the image.
- Bumping resvg changes the Dockerfile hash, rebuilds the image, and
  `just brand-derive` then rewrites the outputs whose bytes changed, which go
  back to review.
- Removing it: render on the host, losing the byte-for-byte check.
