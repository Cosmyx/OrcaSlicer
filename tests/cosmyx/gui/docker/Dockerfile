# Pinned image of the Linux GUI goldens (decisions 0166, 0167).
#
# Everything that changes pixels is fixed here: the base image by digest, the
# packages by an Ubuntu snapshot date, Mesa llvmpipe with one thread and
# 128-bit vectors, one font family, the GTK settings (no caret blink, no
# animations), Xvfb 1600x1000x24 with openbox (started by the harness). The
# same image runs locally (`just goldens-gui-local`) and in CI.
#
# Raising the snapshot date or the digest moves the Linux goldens: do it in
# its own change, with the goldens refreshed and reviewed.
FROM ubuntu:24.04@sha256:73b999393d07f2bf65a40373778a44dc9a6d54ad7718d29247d8ff9413c4d6a8

ARG SNAPSHOT=20261115T000000Z
ENV DEBIAN_FRONTEND=noninteractive

# The snapshot archive is served over HTTPS only, so the CA bundle comes first
# from the base image's own archive; every other package comes from the
# snapshot (the CA bundle too, reinstalled at the snapshot version).
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && echo "APT::Snapshot \"${SNAPSHOT}\";" > /etc/apt/apt.conf.d/50cosmyx-snapshot \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates python3 locales tzdata \
      xvfb xauth x11-apps x11-utils xdotool openbox dbus-x11 \
      libgl1 libgl1-mesa-dri libegl1 libglu1-mesa libopengl0 \
      libgtk-3-0t64 libwebkit2gtk-4.1-0 libsecret-1-0 \
      libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 \
      fonts-dejavu-core \
 && sed -i 's/^# *en_US.UTF-8/en_US.UTF-8/' /etc/locale.gen \
 && locale-gen \
 && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /etc/gtk-3.0 \
 && printf '[Settings]\ngtk-cursor-blink=false\ngtk-enable-animations=false\ngtk-font-name=DejaVu Sans 10\ngtk-theme-name=Adwaita\n' \
      > /etc/gtk-3.0/settings.ini

ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    TZ=UTC \
    LIBGL_ALWAYS_SOFTWARE=1 \
    GALLIUM_DRIVER=llvmpipe \
    LP_NUM_THREADS=1 \
    LP_NATIVE_VECTOR_WIDTH=128 \
    GDK_BACKEND=x11 \
    GDK_SCALE=1 \
    NO_AT_BRIDGE=1 \
    APPIMAGE_EXTRACT_AND_RUN=1

RUN useradd --create-home --uid 1001 goldens
USER goldens
WORKDIR /work
