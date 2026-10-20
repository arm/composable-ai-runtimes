#!/bin/sh
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -eu

cleanup() {
  for pid in "${API_PID:-}" "${NOTIFICATIONS_PID:-}" "${WIREPLUMBER_PID:-}" "${PIPEWIRE_PID:-}"; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT INT TERM

if [ ! -d "$XDG_RUNTIME_DIR" ]; then
  echo "missing runtime directory: $XDG_RUNTIME_DIR" >&2
  echo "fix: ensure /run/pipewire is mounted from the pipewire-runtime volume" >&2
  echo "fix: recreate the runtime volume if needed" >&2
  exit 1
fi

if [ ! -w "$XDG_RUNTIME_DIR" ]; then
  echo "runtime directory is not writable: $XDG_RUNTIME_DIR" >&2
  echo "fix: this usually means the pipewire-runtime volume was created by an older root-based image" >&2
  echo "fix: start the container as root with /usr/local/bin/permissions-set-entrypoint.sh to repair ownership before dropping privileges" >&2
  echo "fix: recreate the runtime volume if repairing ownership is not sufficient" >&2
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

/usr/local/bin/api &
API_PID=$!
/usr/local/bin/notifications &
NOTIFICATIONS_PID=$!

stop_children() {
  kill "$API_PID" "$NOTIFICATIONS_PID" "$WIREPLUMBER_PID" "$PIPEWIRE_PID" 2>/dev/null || true
}

cleanup() {
  trap - INT TERM
  stop_children
  wait "$PIPEWIRE_PID" 2>/dev/null || true
  wait "$WIREPLUMBER_PID" 2>/dev/null || true
  wait "$API_PID" 2>/dev/null || true
  wait "$NOTIFICATIONS_PID" 2>/dev/null || true
}

terminate() {
  cleanup
  exit 143
}

trap 'terminate' INT TERM

while kill -0 "$PIPEWIRE_PID" 2>/dev/null \
  && kill -0 "$WIREPLUMBER_PID" 2>/dev/null \
  && kill -0 "$API_PID" 2>/dev/null \
  && kill -0 "$NOTIFICATIONS_PID" 2>/dev/null; do
  sleep 0.1
done

if ! kill -0 "$PIPEWIRE_PID" 2>/dev/null; then
  if wait "$PIPEWIRE_PID"; then
    exit_status=1
  else
    exit_status=$?
  fi
elif ! kill -0 "$WIREPLUMBER_PID" 2>/dev/null; then
  if wait "$WIREPLUMBER_PID"; then
    exit_status=1
  else
    exit_status=$?
  fi
elif ! kill -0 "$API_PID" 2>/dev/null; then
  if wait "$API_PID"; then
    exit_status=1
  else
    exit_status=$?
  fi
else
  if wait "$NOTIFICATIONS_PID"; then
    exit_status=1
  else
    exit_status=$?
  fi
fi

cleanup
exit "$exit_status"
