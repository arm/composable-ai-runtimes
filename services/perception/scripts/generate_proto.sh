#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/generate_proto.sh [--check]

Generate Python bindings consumed by the Perception Service.

Options:
  --check  Verify that checked-in bindings are current without modifying them.
  -h, --help  Show this help message.
EOF
}

check_only=false

case "${1:-}" in
  "")
    ;;
  --check)
    check_only=true
    ;;
  -h|--help)
    usage
    exit 0
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac

service_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_root="$(cd "${service_dir}/../.." && pwd)"
perception_proto_dir="${service_dir}/proto"
messaging_proto_dir="${repo_root}/services/messaging/proto"
perception_proto="cairn/perception/v1/perception.proto"
messaging_proto="cairn/messaging/v1/messaging.proto"
generated_files=(
  cairn/perception/v1/perception_pb2.py
  cairn/perception/v1/perception_pb2.pyi
  cairn/perception/v1/perception_pb2_grpc.py
  cairn/messaging/v1/messaging_pb2.py
  cairn/messaging/v1/messaging_pb2.pyi
)

if [[ "${check_only}" == true ]]; then
  output_dir="$(mktemp -d)"
  trap 'rm -rf "${output_dir}"' EXIT
else
  output_dir="${service_dir}/src"
fi

(
  cd "${service_dir}"
  uv sync --locked \
    --no-install-package pycairo \
    --no-install-package pygobject
  uv run --no-sync python -m grpc_tools.protoc \
    --proto_path="${perception_proto_dir}" \
    --proto_path="${messaging_proto_dir}" \
    --python_out="${output_dir}" \
    --pyi_out="${output_dir}" \
    "${perception_proto}" \
    "${messaging_proto}"
  uv run --no-sync python -m grpc_tools.protoc \
    --proto_path="${perception_proto_dir}" \
    --grpc_python_out="${output_dir}" \
    "${perception_proto}"
)

if [[ "${check_only}" == false ]]; then
  exit 0
fi

stale_files=()

for generated_file in "${generated_files[@]}"; do
  if ! cmp -s "${service_dir}/src/${generated_file}" "${output_dir}/${generated_file}"; then
    stale_files+=("${generated_file}")
  fi
done

if ((${#stale_files[@]} > 0)); then
  echo "Generated protobuf bindings are stale:" >&2
  printf '  %s\n' "${stale_files[@]}" >&2
  echo "Run: services/perception/scripts/generate_proto.sh" >&2
  exit 1
fi
