#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

case "${1:-}" in
    camera|messaging|perception) ;;
    *) printf 'Usage: bash %s camera|messaging|perception\n' "$0" >&2; exit 2 ;;
esac

generated_notices_dir="$(git rev-parse --show-toplevel)/services/$1/notices/grpc-health-probe"
temp_source_dir="$(mktemp -d "${TMPDIR:-/tmp}/cairn-probe-notices.XXXXXX")"
trap 'rm -rf "$temp_source_dir"' EXIT

# Source recorded in the pinned v0.4.51 image; update with the probe and Go pins.
git init --quiet "$temp_source_dir"
git -C "$temp_source_dir" fetch --quiet --depth 1 https://github.com/grpc-ecosystem/grpc-health-probe.git \
    3ec4030735aeae99976264c18a06f3b6c03ef4f4
git -C "$temp_source_dir" checkout --quiet --detach FETCH_HEAD
rm -rf "$generated_notices_dir"
(
    cd "$temp_source_dir"
    GOOS=linux GOARCH=arm64 CGO_ENABLED=0 GOFLAGS='-mod=readonly -tags=netgo' \
        go-licenses save . --save_path="$generated_notices_dir/modules"
)
cp "$(go env GOROOT)/LICENSE" "$generated_notices_dir/GO-LICENSE"
