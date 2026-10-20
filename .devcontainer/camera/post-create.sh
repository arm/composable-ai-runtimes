#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# Install GStreamer for spoofing cameras.
apt-get update
apt-get install -y --no-install-recommends \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-pipewire \
  wireplumber \
  golang-go
rm -rf /var/lib/apt/lists/*

# Install grpcurl for testing gRPC services from the command line.
go install github.com/fullstorydev/grpcurl/cmd/grpcurl@v1.9.3
ln -sf /root/go/bin/grpcurl /usr/local/bin/grpcurl

# Setup Rust deps.
/usr/local/cargo/bin/rustup component add rustfmt clippy

# Run PipeWire and the same WirePlumber profile used by the camera service image.
mkdir -p /etc/wireplumber/wireplumber.conf.d
cp /workspaces/cairn-sdk/services/camera/config/wireplumber/*.conf /etc/wireplumber/wireplumber.conf.d/
export XDG_RUNTIME_DIR=/run/pipewire
mkdir -p "$XDG_RUNTIME_DIR"
pipewire &
wireplumber &
