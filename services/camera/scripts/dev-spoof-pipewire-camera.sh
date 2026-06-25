#!/usr/bin/env bash
set -euo pipefail

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/pipewire}"

exec gst-launch-1.0 -v \
  multifilesrc location="${PWC_SPOOF_CAMERA_FRAME:-/workspaces/cairn-sdk/services/camera/scripts/sample.jpg}" \
  ! jpegdec \
  ! imagefreeze \
  ! videoconvert \
  ! videoscale \
  ! video/x-raw,format=YUY2,width=640,height=480,framerate=30/1 \
  ! pipewiresink mode=provide async=false use-bufferpool=false \
      client-name=gstreamer-test-source \
      stream-properties="props,media.class=(string)Video/Source,node.name=(string)gstreamer-test-source,node.description=(string)GStreamerTestSource"
