ARG BASE_IMAGE=debian:trixie@sha256:3352c2e13876c8a5c5873ef20870e1939e73cb9a3c1aeba5e3e72172a85ce9ed
ARG PIPEWIRE_VERSION=1.4.10
ARG PIPEWIRE_COMMIT=ced36a5315135044a22c4b373be44368d312f9c8

FROM ${BASE_IMAGE} AS raspberrypi-camera-base

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates=20250419 \
    curl=8.14.1-2+deb13u2 \
    gpg=2.4.7-21+deb13u1+b2 \
  && rm -rf /var/lib/apt/lists/*

# Prefer the Raspberry Pi package line for the camera stack.
RUN mkdir -p /usr/share/keyrings /etc/apt/sources.list.d /etc/apt/preferences.d \
      /etc/crypto-policies/back-ends \
  && printf '%s\n' \
    '[hash_algorithms]' \
    'sha1.second_preimage_resistance = 2028-02-01' \
    > /etc/crypto-policies/back-ends/apt-sequoia.config \
  && curl -fsSL https://archive.raspberrypi.com/debian/raspberrypi.gpg.key \
    -o /tmp/raspberrypi.gpg.key \
  && gpg --dearmor -o /usr/share/keyrings/raspberrypi-archive-keyring.gpg \
    /tmp/raspberrypi.gpg.key \
  && rm -f /tmp/raspberrypi.gpg.key \
  && printf '%s\n' \
    'deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg] https://archive.raspberrypi.com/debian trixie main' \
    > /etc/apt/sources.list.d/raspberrypi.list \
  && printf '%s\n' \
    'Package: *' \
    'Pin: release o=Raspberry Pi Foundation,n=trixie' \
    'Pin-Priority: 100' \
    '' \
    'Package: libcamera* libpisp* pipewire* libpipewire-* libspa-*' \
    'Pin: release o=Raspberry Pi Foundation,n=trixie' \
    'Pin-Priority: 700' \
    > /etc/apt/preferences.d/raspberrypi-camera

FROM raspberrypi-camera-base AS pipewire-build

ARG DEBIAN_FRONTEND=noninteractive
ARG PIPEWIRE_VERSION
ARG PIPEWIRE_COMMIT

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.12 \
    gettext-base \
    git \
    libcamera-dev=0.7.0+rpt20260205-1 \
    libdbus-1-dev=1.16.2-2 \
    libglib2.0-dev=2.84.4-3~deb13u2 \
    libudev-dev \
    meson \
    ninja-build \
    pkg-config=1.8.1-4 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /tmp
RUN git clone --branch "${PIPEWIRE_VERSION}" --depth 1 \
      https://gitlab.freedesktop.org/pipewire/pipewire.git pipewire-src \
  && test "$(git -C pipewire-src rev-parse HEAD)" = "${PIPEWIRE_COMMIT}"

WORKDIR /tmp/pipewire-src
RUN arch="$(dpkg-architecture -qDEB_HOST_MULTIARCH)" \
  && meson setup build \
      --prefix=/usr \
      --libdir="/usr/lib/${arch}" \
      -Ddocs=disabled \
      -Dman=disabled \
      -Dexamples=disabled \
      -Dtests=disabled \
      -Dsession-managers=[] \
      -Dlibcamera=enabled \
      -Drlimits-install=false \
  && meson compile -C build \
  && DESTDIR=/opt/pipewire-root meson install -C build

FROM raspberrypi-camera-base AS camera-service-build

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.12 \
    libgrpc++-dev=1.51.1-6 \
    libprotobuf-dev=3.21.12-11 \
    pkg-config=1.8.1-4 \
    protobuf-compiler=3.21.12-11 \
    protobuf-compiler-grpc=1.51.1-6 \
  && rm -rf /var/lib/apt/lists/*

COPY --from=pipewire-build /opt/pipewire-root/usr/ /usr/

WORKDIR /src/pipewire
COPY pipewire/ ./
RUN make

FROM raspberrypi-camera-base AS camera-service-runtime

ARG DEBIAN_FRONTEND=noninteractive
ARG CAMERA_SERVICE_UID=10001
ARG CAMERA_SERVICE_GID=10001

RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2t64=1.2.14-1 \
    libavahi-client3=0.8-16 \
    libcap2-bin=1:2.75-10+b8 \
    libdbus-1-3=1.16.2-2 \
    libdrm2=2.4.124-2 \
    libgbm1=25.0.7-2 \
    libglib2.0-0t64=2.84.4-3~deb13u2 \
    libgrpc++1.51t64=1.51.1-6 \
    libcamera-ipa=0.7.0+rpt20260205-1 \
    libcamera-v4l2=0.7.0+rpt20260205-1 \
    libcamera0.7=0.7.0+rpt20260205-1 \
    libpisp1=1.4.0-1 \
    libprotobuf32t64=3.21.12-11 \
    libsystemd0 \
    libudev1 \
    libunwind8=1.8.1-0.1 \
    libv4l-0t64=1.30.1-1 \
    wireplumber=0.5.8-2 \
  && apt-get purge -y --auto-remove curl gpg \
  && rm -f /etc/apt/sources.list.d/raspberrypi.list \
           /etc/apt/preferences.d/raspberrypi-camera \
           /usr/share/keyrings/raspberrypi-archive-keyring.gpg \
           /etc/crypto-policies/back-ends/apt-sequoia.config \
  && rm -rf /var/lib/apt/lists/*

COPY --from=pipewire-build /opt/pipewire-root/usr/ /usr/

RUN groupadd --system --gid "${CAMERA_SERVICE_GID}" camera-service \
  && useradd --system --uid "${CAMERA_SERVICE_UID}" --gid camera-service --groups video \
      --create-home --home-dir /home/camera-service --shell /usr/sbin/nologin camera-service \
  && mkdir -p /run/pipewire \
  && chown -R camera-service:camera-service /home/camera-service /run/pipewire \
  && chmod 711 /run/pipewire

ENV HOME=/home/camera-service \
    USER=camera-service \
    LOGNAME=camera-service \
    XDG_RUNTIME_DIR=/run/pipewire

COPY config/libcamera/configuration.yaml /etc/libcamera/configuration.yaml
COPY config/pipewire/ /etc/pipewire/pipewire.conf.d/
COPY config/wireplumber/ /etc/wireplumber/wireplumber.conf.d/

COPY --from=camera-service-build /src/pipewire/server /usr/local/bin/server
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY scripts/permissions-set-entrypint.sh /usr/local/bin/permissions-set-entrypint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/permissions-set-entrypint.sh /usr/local/bin/server \
  && setcap cap_sys_nice=ep /usr/bin/pipewire \
  && setcap cap_sys_nice=ep /usr/bin/wireplumber \
  && ldconfig

USER camera-service

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
