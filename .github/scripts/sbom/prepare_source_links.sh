#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

if [[ $# -eq 0 || "$1" == "--help" ]]; then
  printf 'Usage: bash %s REPOSITORY_IMAGE --image IMAGE --output REPORT SBOM...\n' "$0"
  printf 'REPOSITORY_IMAGE must have the matching apt repositories and signing keys configured.\n'
  if [[ $# -eq 0 ]]; then
    exit 2
  fi
  exit 0
fi

repository_image="$1"
shift
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

source_container="$(docker run --rm -d --user 0 --entrypoint sleep \
  "$repository_image" infinity)"
trap 'docker stop "$source_container" >/dev/null' EXIT

docker exec "$source_container" sh -ec '
  sed -i -e "s/^Types: deb$/Types: deb-src/" -e "s/^deb /deb-src /" \
    /etc/apt/sources.list.d/*
  apt-get -o APT::Update::Error-Mode=any update
'

uv run --no-project python "$script_dir/source_links.py" \
  --apt-container "$source_container" "$@"
