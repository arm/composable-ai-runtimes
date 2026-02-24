FROM dtcooper/raspberrypi-os:bookworm

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    dbus \
    libcamera0.4 \
    libcamera-ipa \
    libcamera-v4l2 \
    libv4l-0 \
    libgbm1 \
    libdrm2 \
    libspa-0.2-libcamera \
    libspa-0.2-modules \
    pipewire \
    rtkit \
    wireplumber \
  && rm -rf /var/lib/apt/lists/*

ENV XDG_RUNTIME_DIR=/run/pipewire
ENV PIPEWIRE_NO_PORTAL=1

RUN mkdir -p /etc/pipewire/pipewire.conf.d

COPY scripts/start-pipewire.sh /usr/local/bin/start-pipewire.sh
COPY config/wireplumber/10-disable-bluetooth.conf /etc/wireplumber/wireplumber.conf.d/10-disable-bluetooth.conf
COPY config/wireplumber/60-disable-portal.lua /etc/wireplumber/main.lua.d/60-disable-portal.lua
RUN chmod +x /usr/local/bin/start-pipewire.sh

ENTRYPOINT ["/usr/local/bin/start-pipewire.sh"]
