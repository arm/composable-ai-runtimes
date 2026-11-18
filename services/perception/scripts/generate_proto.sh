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
media_proto_dir="${repo_root}/services/media/proto"
perception_proto="cairn/perception/v1/perception.proto"
messaging_proto="cairn/messaging/v1/messaging.proto"
media_proto="cairn/media/v1/stream_configuration.proto"
perception_python_proto_path="perception_service/_proto"
generated_files=(
  "${perception_python_proto_path}/perception/v1/perception_pb2.py"
  "${perception_python_proto_path}/perception/v1/perception_pb2.pyi"
  "${perception_python_proto_path}/perception/v1/perception_pb2_grpc.py"
  "${perception_python_proto_path}/messaging/v1/messaging_pb2.py"
  "${perception_python_proto_path}/messaging/v1/messaging_pb2.pyi"
  "${perception_python_proto_path}/media/v1/stream_configuration_pb2.py"
  "${perception_python_proto_path}/media/v1/stream_configuration_pb2.pyi"
)

temp_dir="$(mktemp -d)"
trap 'rm -rf "${temp_dir}"' EXIT
proto_input_dir="${temp_dir}/proto"
# Stage private import paths without changing the published protobuf contracts.
for proto_source in \
  "${perception_proto_dir}/${perception_proto}" \
  "${messaging_proto_dir}/${messaging_proto}" \
  "${media_proto_dir}/${media_proto}"; do
  staged_proto="${proto_input_dir}/${perception_python_proto_path}/${proto_source#*/proto/cairn/}"
  mkdir -p "$(dirname "${staged_proto}")"
  sed "s@\"cairn/@\"${perception_python_proto_path}/@g" "${proto_source}" > "${staged_proto}"
done

if [[ "${check_only}" == true ]]; then
  output_dir="${temp_dir}/generated"
  mkdir -p "${output_dir}"
else
  output_dir="${service_dir}/src"
fi

(
  cd "${service_dir}"
  uv sync --project "${repo_root}" --locked --only-group proto
  uv run --project "${repo_root}" --no-sync python -m grpc_tools.protoc \
    --proto_path="${proto_input_dir}" \
    --python_out="${output_dir}" \
    --pyi_out="${output_dir}" \
    "${perception_python_proto_path}/${perception_proto#cairn/}" \
    "${perception_python_proto_path}/${messaging_proto#cairn/}" \
    "${perception_python_proto_path}/${media_proto#cairn/}"
  uv run --project "${repo_root}" --no-sync python -m grpc_tools.protoc \
    --proto_path="${proto_input_dir}" \
    --grpc_python_out="${output_dir}" \
    "${perception_python_proto_path}/${perception_proto#cairn/}"
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
