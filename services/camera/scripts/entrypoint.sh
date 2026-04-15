#!/bin/sh
set -eu

if [ ! -d "$XDG_RUNTIME_DIR" ]; then
  echo "missing runtime directory: $XDG_RUNTIME_DIR" >&2
  echo "fix: ensure /run/pipewire is mounted from the pipewire-runtime volume in services/camera/compose.yaml" >&2
  echo "fix: recreate the runtime volume with 'docker compose -f services/camera/compose.yaml down && docker volume rm camera_pipewire-runtime'" >&2
  exit 1
fi

if [ ! -w "$XDG_RUNTIME_DIR" ]; then
  echo "runtime directory is not writable: $XDG_RUNTIME_DIR" >&2
  echo "fix: this usually means the pipewire-runtime volume was created by an older root-based image" >&2
  echo "fix: start the container as root with /usr/local/bin/permissions-set-entrypint.sh to repair ownership before dropping privileges" >&2
  echo "fix: recreate it with 'docker compose -f services/camera/compose.yaml down && docker volume rm camera_pipewire-runtime'" >&2
  exit 1
fi

pipewire &
PIPEWIRE_PID=$!
TIMEOUT_TENTHS=50
for _ in $(seq 1 "$TIMEOUT_TENTHS"); do
  if pw-dump 0 >/dev/null 2>&1; then
    break
  fi
  sleep 0.1
done
if ! pw-dump 0 >/dev/null 2>&1; then
  echo "pipewire did not become ready within timeout" >&2
  exit 1
fi

# Allow non-root client containers to connect to the public PipeWire socket on the shared runtime volume.
chmod 666 "$XDG_RUNTIME_DIR"/pipewire-0

wireplumber &
WIREPLUMBER_PID=$!

/usr/local/bin/server &
CAMERA_MONITOR_PID=$!

while true; do
  if ! kill -0 "$PIPEWIRE_PID" 2>/dev/null; then
    echo "pipewire exited" >&2
    exit 1
  fi
  if ! kill -0 "$WIREPLUMBER_PID" 2>/dev/null; then
    echo "wireplumber exited" >&2
    exit 1
  fi
  if ! kill -0 "$CAMERA_MONITOR_PID" 2>/dev/null; then
    echo "server exited" >&2
    exit 1
  fi
  sleep 1
done
