#!/bin/sh
set -eu

/usr/local/bin/api &
api_pid=$!
/usr/local/bin/notifications &
notifications_pid=$!

stop_children() {
  kill "$api_pid" "$notifications_pid" 2>/dev/null || true
}

cleanup() {
  trap - INT TERM
  stop_children
  wait "$api_pid" 2>/dev/null || true
  wait "$notifications_pid" 2>/dev/null || true
}

terminate() {
  cleanup
  exit 143
}

trap 'terminate' INT TERM

while kill -0 "$api_pid" 2>/dev/null && kill -0 "$notifications_pid" 2>/dev/null; do
  sleep 0.1
done

if ! kill -0 "$api_pid" 2>/dev/null; then
  if wait "$api_pid"; then
    exit_status=1
  else
    exit_status=$?
  fi
else
  if wait "$notifications_pid"; then
    exit_status=1
  else
    exit_status=$?
  fi
fi

cleanup
exit "$exit_status"
