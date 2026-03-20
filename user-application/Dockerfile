FROM rust:1.93-slim AS rust-toolchain

FROM python:3.12-slim AS sdk-builder

ENV DEBIAN_FRONTEND=noninteractive

COPY --from=rust-toolchain /usr/local/cargo /usr/local/cargo
COPY --from=rust-toolchain /usr/local/rustup /usr/local/rustup
ENV PATH=/usr/local/cargo/bin:${PATH}

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    clang \
    libclang-dev \
    libpipewire-0.3-dev \
    libprotobuf-dev \
    libspa-0.2-dev \
    pkg-config \
    protobuf-compiler \
    python3-dev \
  && rm -rf /var/lib/apt/lists/*

RUN python3 -m pip install --no-cache-dir --upgrade pip \
 && python3 -m pip install --no-cache-dir maturin

WORKDIR /src

# The Rust SDK build depends on protobuf sources outside lib/.
COPY lib /src/lib
COPY services/concordia/src/inference/proto /src/services/concordia/src/inference/proto
COPY services/camera/pipewire/proto /src/services/camera/pipewire/proto

WORKDIR /src/lib
RUN maturin build --release --auditwheel skip -o /dist

FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV XDG_RUNTIME_DIR=/run/pipewire
ENV SPA_PLUGIN_DIR=/usr/lib/aarch64-linux-gnu/spa-0.2

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpipewire-0.3-0 \
    libspa-0.2-modules \
    pipewire \
    pipewire-bin \
    libasound2t64 \
    libavahi-client3 \
    libcamera0.4 \
    libcamera-v4l2 \
    libdrm2 \
    libgbm1 \
    libglib2.0-0t64 \
    libprotobuf32t64 \
    libsystemd0 \
    libudev1 \
    libv4l-0t64 \
    dbus \
    rtkit \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=sdk-builder /dist/cairn_sdk_lib-*.whl /tmp/
RUN python3 -m pip install --no-cache-dir /tmp/cairn_sdk_lib-*.whl \
 && rm -f /tmp/cairn_sdk_lib-*.whl

CMD ["/bin/bash"]
