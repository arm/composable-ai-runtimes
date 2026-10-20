#!/bin/sh
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -eu

mkdir -p "$XDG_RUNTIME_DIR"
chmod 755 "$XDG_RUNTIME_DIR"

pipewire &

for _ in $(seq 1 100); do
  if pw-dump 0 >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done
if ! pw-dump 0 >/dev/null 2>&1; then
  echo "PipeWire did not become ready" >&2
  exit 1
fi

chmod 666 "$XDG_RUNTIME_DIR/pipewire-0"
wireplumber &

exec gst-launch-1.0 -q \
  filesrc location=/sample_input.jpg ! jpegdec ! imagefreeze is-live=true \
  ! videoscale ! videoconvert \
  ! video/x-raw,format=YUY2,width=640,height=480,framerate=30/1 \
  ! pipewiresink mode=provide async=false use-bufferpool=false \
      client-name=gstreamer-test-source \
      stream-properties="props,media.class=(string)Video/Source,node.name=(string)gstreamer-test-source,node.description=(string)GStreamerTestSource"
