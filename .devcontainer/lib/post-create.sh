#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  libclang-common-19-dev \
  libclang1-19 \
  libpipewire-0.3-dev \
  pipewire-bin \
  pkg-config \
  protobuf-compiler
rm -rf /var/lib/apt/lists/*

/usr/local/bin/python3 -m venv /opt/cairn-sdk-venv
/opt/cairn-sdk-venv/bin/python -m pip install --no-cache-dir \
  "maturin>=1.7,<2.0" \
  "uv==0.13.5"

/usr/local/cargo/bin/rustup component add rustfmt clippy
/usr/local/cargo/bin/rustup toolchain install 1.99.1 --component rustfmt --component clippy
