#!/bin/sh
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "permission entrypoint must start as root" >&2
  exit 1
fi

if ! command -v setpriv >/dev/null 2>&1; then
  echo "missing required tool: setpriv" >&2
  exit 1
fi

MEDIA_SERVICE_UID=$(id -u media-service)
MEDIA_SERVICE_GID=$(id -g media-service)

if [ ! -e "$XDG_RUNTIME_DIR" ]; then
  mkdir -p "$XDG_RUNTIME_DIR"
fi

chown -R media-service:media-service "$XDG_RUNTIME_DIR"
chmod 711 "$XDG_RUNTIME_DIR"

if [ "$#" -gt 0 ]; then
  exec setpriv --reuid "$MEDIA_SERVICE_UID" --regid "$MEDIA_SERVICE_GID" --init-groups "$@"
fi

exec setpriv --reuid "$MEDIA_SERVICE_UID" --regid "$MEDIA_SERVICE_GID" --init-groups /usr/local/bin/entrypoint.sh
