#!/bin/sh
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -eu

cleanup() {
  trap - EXIT INT TERM

  for pid in "${API_PID:-}" "${REDIS_PID:-}"; do
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done

  for pid in "${API_PID:-}" "${REDIS_PID:-}"; do
    if [ -n "$pid" ]; then
      wait "$pid" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT INT TERM

redis-server /usr/local/etc/redis/redis.conf &
REDIS_PID=$!

/usr/local/bin/api &
API_PID=$!

terminate() {
  cleanup
  exit 143
}

trap 'terminate' INT TERM

while kill -0 "$REDIS_PID" 2>/dev/null && kill -0 "$API_PID" 2>/dev/null; do
  sleep 0.1
done

if ! kill -0 "$REDIS_PID" 2>/dev/null; then
  if wait "$REDIS_PID"; then
    exit_status=1
  else
    exit_status=$?
  fi
else
  if wait "$API_PID"; then
    exit_status=1
  else
    exit_status=$?
  fi
fi

cleanup
exit "$exit_status"
