ARG BASE_IMAGE=docker.io/library/debian:trixie@sha256:3352c2e13876c8a5c5873ef20870e1939e73cb9a3c1aeba5e3e72172a85ce9ed
ARG RUST_IMAGE=docker.io/library/rust:1.93.1-trixie@sha256:ecbe59a8408895edd02d9ef422504b8501dd9fa1526de27a45b73406d734d659
ARG PIPEWIRE_VERSION=1.4.10
ARG PIPEWIRE_COMMIT=ced36a5315135044a22c4b373be44368d312f9c8
ARG RPI_LIBCAMERA_VERSION=0.7.1+rpt20260609-1

FROM ${BASE_IMAGE} AS raspberrypi-camera-base

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates=20250419 \
    curl=8.14.1-2+deb13u3 \
    gpg=2.4.7-21+deb13u1+b3 \
  && rm -rf /var/lib/apt/lists/*

# Prefer the Raspberry Pi package line for the camera stack.
COPY scripts/docker-configure-raspberrypi-apt.sh /tmp/configure-raspberrypi-apt.sh
RUN sh /tmp/configure-raspberrypi-apt.sh \
  && rm -f /tmp/configure-raspberrypi-apt.sh

FROM raspberrypi-camera-base AS pipewire-build

ARG DEBIAN_FRONTEND=noninteractive
ARG PIPEWIRE_VERSION
ARG PIPEWIRE_COMMIT
ARG RPI_LIBCAMERA_VERSION

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.12 \
    gettext-base=0.23.1-2 \
    git=1:2.47.3-0+deb13u1 \
    libcamera-dev="${RPI_LIBCAMERA_VERSION}" \
    libdbus-1-dev=1.16.2-2 \
    libglib2.0-dev=2.84.4-3~deb13u3 \
    libudev-dev=257.13-1~deb13u1 \
    meson=1.7.0-1 \
    ninja-build=1.12.1-1+b1 \
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

FROM ${RUST_IMAGE} AS camera-service-build

ARG DEBIAN_FRONTEND=noninteractive

WORKDIR /src

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.12 \
    libclang-common-19-dev=1:19.1.7-3+b1 \
    libclang1-19=1:19.1.7-3+b1 \
    libdbus-1-dev=1.16.2-2 \
    libglib2.0-dev=2.84.4-3~deb13u3 \
    libudev-dev=257.13-1~deb13u1 \
    pkg-config=1.8.1-4 \
    protobuf-compiler=3.21.12-11 \
  && rm -rf /var/lib/apt/lists/*

COPY --from=pipewire-build /opt/pipewire-root/usr/ /usr/
COPY Cargo.toml Cargo.lock build.rs ./
COPY proto ./proto
COPY src ./src

RUN cargo build --locked --release --bins

FROM raspberrypi-camera-base AS camera-service-runtime

ARG DEBIAN_FRONTEND=noninteractive
ARG CAMERA_SERVICE_UID=10001
ARG CAMERA_SERVICE_GID=10001
ARG RPI_LIBCAMERA_VERSION

RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2t64=1.2.14-1 \
    libavahi-client3=0.8-16 \
    libcamera-ipa="${RPI_LIBCAMERA_VERSION}" \
    libcamera-v4l2="${RPI_LIBCAMERA_VERSION}" \
    libcamera0.7="${RPI_LIBCAMERA_VERSION}" \
    libcap2-bin=1:2.75-10+deb13u1+b1 \
    libdbus-1-3=1.16.2-2 \
    libdrm2=2.4.124-2 \
    libgbm1=25.0.7-2 \
    libglib2.0-0t64=2.84.4-3~deb13u3 \
    libpisp1=1.5.0-1 \
    libsystemd0=257.13-1~deb13u1 \
    libudev1=257.13-1~deb13u1 \
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
COPY --from=camera-service-build /src/target/release/api /usr/local/bin/api
COPY --from=camera-service-build /src/target/release/notifications /usr/local/bin/notifications
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY scripts/permissions-set-entrypint.sh /usr/local/bin/permissions-set-entrypint.sh

RUN chmod +x /usr/local/bin/api /usr/local/bin/notifications /usr/local/bin/entrypoint.sh /usr/local/bin/permissions-set-entrypint.sh \
  && setcap cap_sys_nice=ep /usr/bin/pipewire \
  && setcap cap_sys_nice=ep /usr/bin/wireplumber \
  && ldconfig

USER camera-service

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
