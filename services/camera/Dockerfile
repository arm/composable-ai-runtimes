ARG BASE_IMAGE=dtcooper/raspberrypi-os:bookworm@sha256:8e710ae87812a1c3dfe20e48470130f74e57cdd66d9d08e8d292fcf42d447243

FROM ${BASE_IMAGE} AS pipewire-build

ARG DEBIAN_FRONTEND=noninteractive
ARG PIPEWIRE_COMMIT=d20a1523b6770dfa93a270bdda5d7c800d7ec191

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential=12.9 \
    ca-certificates=20230311+deb12u1 \
    dbus=1.14.10-1~deb12u1 \
    gettext=0.21-12 \
    git=1:2.39.5-0+deb12u3 \
    libcamera-dev=0.5.2+rpt20250903-1~bpo12+1 \
    libdbus-1-dev=1.14.10-1~deb12u1 \
    libdrm-dev=2.4.123-1~bpo12+1+rpt1 \
    libgbm-dev=24.2.8-1~bpo12+rpt4 \
    libglib2.0-dev=2.74.6-2+deb12u8 \
    libsystemd-dev=252.39-1~deb12u1 \
    libudev-dev=252.39-1~deb12u1 \
    libv4l-dev=1.22.1-5+b2 \
    meson=1.5.1-1~bpo12+1~rpt1 \
    ninja-build=1.11.1-2~deb12u1 \
    pkg-config=1.8.1-1 \
    python3=3.11.2-1+b1 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /src
RUN git clone https://gitlab.freedesktop.org/pipewire/pipewire.git pipewire \
  && git -C pipewire checkout --detach "${PIPEWIRE_COMMIT}"

WORKDIR /src/pipewire
RUN meson setup build \
      --prefix=/usr \
      --libdir=lib/aarch64-linux-gnu \
      --sysconfdir=/etc \
      --localstatedir=/var \
      --buildtype=release \
  && meson compile -C build \
  && meson install -C build \
  && DESTDIR=/pipewire-install meson install -C build \
  && ldconfig

FROM pipewire-build AS camera-service-build

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgrpc++-dev=1.51.1-3+b1 \
    libprotobuf-dev=3.21.12-3 \
    protobuf-compiler=3.21.12-3 \
    protobuf-compiler-grpc=1.51.1-3+b1 \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /src/pipewire
COPY pipewire/ ./
RUN make

FROM ${BASE_IMAGE}

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    dbus=1.14.10-1~deb12u1 \
    libasound2=1.2.8-1+rpt1 \
    libavahi-client3=0.8-10+deb12u1 \
    libcamera0.4=0.4.0+rpt20250213-1 \
    libcamera-ipa=0.5.2+rpt20250903-1~bpo12+1 \
    libcamera-v4l2=0.5.2+rpt20250903-1~bpo12+1 \
    libdbus-1-3=1.14.10-1~deb12u1 \
    libglib2.0-0=2.74.6-2+deb12u8 \
    libgrpc++1.51=1.51.1-3+b1 \
    libprotobuf32=3.21.12-3 \
    libsystemd0=252.39-1~deb12u1 \
    libudev1=252.39-1~deb12u1 \
    libv4l-0=1.22.1-5+b2 \
    rtkit=0.13-5 \
  && rm -rf /var/lib/apt/lists/*

ENV XDG_RUNTIME_DIR=/run/pipewire
ENV PIPEWIRE_NO_PORTAL=1

COPY --from=pipewire-build /pipewire-install/usr/ /usr/
COPY --from=pipewire-build /pipewire-install/etc/ /etc/
COPY config/pipewire/ /etc/pipewire/pipewire.conf.d/
COPY config/wireplumber/ /etc/wireplumber/wireplumber.conf.d/

COPY --from=camera-service-build /src/pipewire/server /usr/local/bin/server
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/server \
  && ldconfig

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
