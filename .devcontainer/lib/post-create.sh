#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  libclang-common-19-dev=1:19.1.7-3+b1 \
  libclang1-19=1:19.1.7-3+b1 \
  libpipewire-0.3-dev=1.4.2-1 \
  pipewire-bin=1.4.2-1 \
  pkg-config=1.8.1-4 \
  protobuf-compiler=3.21.12-11

/usr/local/cargo/bin/rustup component add rustfmt clippy
/usr/local/cargo/bin/rustup toolchain install 1.93 --component rustfmt --component clippy
