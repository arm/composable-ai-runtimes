#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROTO_DIR="${ROOT_DIR}/src/inference/proto"
PROTO_FILES=(
  "${PROTO_DIR}/concordia.proto"
)
OUT_DIR="${PROTO_DIR}"

python -m grpc_tools.protoc \
  -I "${PROTO_DIR}" \
  --python_out="${OUT_DIR}" \
  --pyi_out="${OUT_DIR}" \
  --grpc_python_out="${OUT_DIR}" \
  "${PROTO_FILES[@]}"
