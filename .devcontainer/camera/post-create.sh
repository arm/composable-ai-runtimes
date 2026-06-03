#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# Install GStreamer for spoofing cameras.
apt-get update
apt-get install -y --no-install-recommends \
  gstreamer1.0-tools=1.26.2-2 \
  gstreamer1.0-plugins-base=1.26.2-1+deb13u1 \
  gstreamer1.0-plugins-good=1.26.2-1 \
  gstreamer1.0-pipewire=1.4.2-1 \
  wireplumber=0.5.8-2 \
  golang-go

# Install grpcurl for testing gRPC services from the command line.
go install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest
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
