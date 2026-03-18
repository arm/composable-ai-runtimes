#!/bin/sh
set -eu

mkdir -p "$XDG_RUNTIME_DIR" /run/dbus
chmod 700 "$XDG_RUNTIME_DIR"
chmod 755 /run/dbus

if [ ! -s /etc/machine-id ]; then
  dbus-uuidgen --ensure=/etc/machine-id
fi

dbus-daemon --system --nofork --nopidfile &
dbus-daemon --session --address=unix:path=/run/dbus/session_bus_socket --nofork --nopidfile &
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/dbus/session_bus_socket

if command -v rtkit-daemon >/dev/null 2>&1; then
  rtkit-daemon &
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
