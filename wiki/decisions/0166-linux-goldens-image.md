# 0166. Linux goldens run in a pinned Docker image

## Status

Accepted.

## Context

Byte-exact goldens need the same pixels on every run and every machine.

## Decision

- `tests/cosmyx/gui/docker/Dockerfile`: `ubuntu:24.04` pinned by digest, every
  package from one Ubuntu snapshot date (the CA bundle is fetched first from
  the base image's archive, because the snapshot is served over HTTPS only),
  Mesa llvmpipe with `LP_NUM_THREADS=1` and `LP_NATIVE_VECTOR_WIDTH=128`,
  `GDK_BACKEND=x11`, DejaVu fonts, the pinned WebKitGTK, GTK settings with no
  caret blink and no animations, en_US.UTF-8 and UTC.
- The harness starts Xvfb `1600x1000x24` and openbox inside it.
- CI and `just goldens-gui-local` build and run the same `linux/amd64` image.

## Consequences

- Raising the digest or the snapshot date moves the Linux goldens: it is its
  own change, with the goldens refreshed and reviewed.
- On Apple Silicon the image is emulated; CI stays the reference.
