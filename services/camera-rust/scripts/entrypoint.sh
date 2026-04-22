#!/bin/sh
set -eu

/usr/local/bin/grpc &
grpc_pid=$!
/usr/local/bin/notifications &
notifications_pid=$!

stop_children() {
  kill "$grpc_pid" "$notifications_pid" 2>/dev/null || true
}

cleanup() {
  trap - INT TERM
  stop_children
  wait "$grpc_pid" 2>/dev/null || true
  wait "$notifications_pid" 2>/dev/null || true
}

terminate() {
  cleanup
  exit 143
}

trap 'terminate' INT TERM

while kill -0 "$grpc_pid" 2>/dev/null && kill -0 "$notifications_pid" 2>/dev/null; do
  sleep 0.1
done

if ! kill -0 "$grpc_pid" 2>/dev/null; then
  if wait "$grpc_pid"; then
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
