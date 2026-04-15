ARG BASE_IMAGE=debian:trixie@sha256:3352c2e13876c8a5c5873ef20870e1939e73cb9a3c1aeba5e3e72172a85ce9ed
ARG LIBCAMERA_GIT_REF=v0.4.0+rpt20250213 # 29156679717bec7cc4784aeba3548807f2c27fca

FROM ${BASE_IMAGE} AS libcamera-build

ARG DEBIAN_FRONTEND=noninteractive
ARG LIBCAMERA_GIT_REF

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.12 \
    ca-certificates=20250419 \
    git=1:2.47.3-0+deb13u1 \
    libcap-dev=1:2.75-10+b8 \
    libdrm-dev=2.4.124-2 \
    libdw-dev=0.192-4 \
    libexpat1-dev=2.7.1-2 \
    libglib2.0-dev=2.84.4-3~deb13u2 \
    libgnutls28-dev=3.8.9-3+deb13u2 \
    libjpeg-dev=1:2.1.5-4 \
    liblttng-ust-dev=2.13.9-1 \
    libudev-dev=257.9-1~deb13u1 \
    libunwind-dev=1.8.1-0.1 \
    libyaml-dev=0.2.5-2 \
    meson=1.7.0-1 \
    ninja-build=1.12.1-1+b1 \
    pkg-config=1.8.1-4 \
    python3-jinja2=3.1.6-1 \
    python3-ply=3.11-9 \
    python3-yaml=6.0.2-1+b2 \
  && rm -rf /var/lib/apt/lists/*

RUN git clone --branch "${LIBCAMERA_GIT_REF}" --depth 1 \
      https://github.com/raspberrypi/libcamera.git /src/libcamera

RUN meson setup /src/libcamera/build /src/libcamera \
      -Dcam=disabled \
      -Ddocumentation=disabled \
      -Dgstreamer=disabled \
      -Dipas=rpi/vc4,rpi/pisp \
      -Dlc-compliance=disabled \
      -Dpipelines=rpi/vc4,rpi/pisp \
      -Dqcam=disabled \
      -Dtest=false \
      -Dv4l2=true \
  && ninja -C /src/libcamera/build \
  && DESTDIR=/tmp/libcamera-install ninja -C /src/libcamera/build install

FROM ${BASE_IMAGE} AS camera-service-build

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.12 \
    libgrpc++-dev=1.51.1-6 \
    libpipewire-0.3-dev=1.4.2-1 \
    libprotobuf-dev=3.21.12-11 \
    pkg-config=1.8.1-4 \
    protobuf-compiler=3.21.12-11 \
    protobuf-compiler-grpc=1.51.1-6 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /src/pipewire
COPY pipewire/ ./
RUN make

FROM ${BASE_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    dbus=1.16.2-2 \
    libasound2t64=1.2.14-1 \
    libavahi-client3=0.8-16 \
    libdbus-1-3=1.16.2-2 \
    libdrm2=2.4.124-2 \
    libgbm1=25.0.7-2 \
    libglib2.0-0t64=2.84.4-3~deb13u2 \
    libgrpc++1.51t64=1.51.1-6 \
    libpipewire-0.3-0t64=1.4.2-1 \
    libprotobuf32t64=3.21.12-11 \
    libspa-0.2-libcamera=1.4.2-1 \
    libunwind8=1.8.1-0.1 \
    libv4l-0t64=1.30.1-1 \
    pipewire=1.4.2-1 \
    rtkit=0.13-5.1+b1 \
    wireplumber=0.5.8-2 \
  && rm -rf /var/lib/apt/lists/*

ENV XDG_RUNTIME_DIR=/run/pipewire
ENV PIPEWIRE_NO_PORTAL=1

COPY config/pipewire/ /etc/pipewire/pipewire.conf.d/
COPY config/wireplumber/ /etc/wireplumber/wireplumber.conf.d/

COPY --from=libcamera-build /tmp/libcamera-install/ /
COPY --from=camera-service-build /src/pipewire/server /usr/local/bin/server
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/server \
  && ldconfig

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
