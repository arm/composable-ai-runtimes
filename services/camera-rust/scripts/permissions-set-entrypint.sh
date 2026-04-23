#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "permission entrypoint must start as root" >&2
  exit 1
fi

if ! command -v setpriv >/dev/null 2>&1; then
  echo "missing required tool: setpriv" >&2
  exit 1
fi

CAMERA_SERVICE_UID=$(id -u camera-service)
CAMERA_SERVICE_GID=$(id -g camera-service)

if [ ! -e "$XDG_RUNTIME_DIR" ]; then
  mkdir -p "$XDG_RUNTIME_DIR"
fi

chown -R camera-service:camera-service "$XDG_RUNTIME_DIR"
chmod 711 "$XDG_RUNTIME_DIR"

if [ "$#" -gt 0 ]; then
  exec setpriv --reuid "$CAMERA_SERVICE_UID" --regid "$CAMERA_SERVICE_GID" --init-groups "$@"
fi

exec setpriv --reuid "$CAMERA_SERVICE_UID" --regid "$CAMERA_SERVICE_GID" --init-groups /usr/local/bin/entrypoint.sh
