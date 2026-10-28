#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

if (( $# == 0 )); then
  check_only=false
elif (( $# == 1 )) && [[ "$1" == --check ]]; then
  check_only=true
else
  echo "Usage: $0 [--check]" >&2
  exit 2
fi

cd "$(dirname "$0")/../../../lib"
if [[ "$(cargo sbom --version)" != 'cargo-sbom 0.10.0' ]]; then
  echo 'Install the pinned generator: cargo install cargo-sbom --version 0.10.0 --locked' >&2
  exit 1
fi

temp_dir=$(mktemp -d)
trap 'rm -rf "$temp_dir"' EXIT

cp Cargo.lock "$temp_dir/Cargo.lock"
cargo metadata --locked --format-version 1 > /dev/null

# Remove host-specific attribution and stabilize unordered collections.
normalize_filter='
  del(.metadata.authors)
  | .components |= sort_by(."bom-ref")
  | .metadata.component.components |= sort_by(."bom-ref")
  | .dependencies |= (sort_by(.ref) | map(.dependsOn |= sort))
'
# Generation time and document UUID do not describe dependency changes.
ignore_volatile_filter='del(.serialNumber, .metadata.timestamp)'

for crate in cairn-camera cairn-notification cairn-perception cairn; do
  sbom_path="crates/$crate/bom.json"
  # Generate separately so a failure cannot overwrite the committed SBOM.
  cargo sbom \
    --cargo-package "arm-$crate" \
    --project-directory . \
    --output-format cyclone_dx_json_1_6 > "$temp_dir/generated.json"
  if ! cmp -s Cargo.lock "$temp_dir/Cargo.lock"; then
    echo 'cargo-sbom unexpectedly modified Cargo.lock. Review the changes, then regenerate the SBOMs.' >&2
    exit 1
  fi
  jq -S "$normalize_filter" "$temp_dir/generated.json" > "$temp_dir/sorted.json"

  if [[ "$check_only" == false ]]; then
    cp "$temp_dir/sorted.json" "$sbom_path"
    echo "Generated lib/$sbom_path; review and commit it."
    continue
  fi

  jq -S "$normalize_filter | $ignore_volatile_filter" "$sbom_path" > "$temp_dir/committed.json"
  jq -S "$ignore_volatile_filter" "$temp_dir/sorted.json" > "$temp_dir/current.json"
  if ! diff -u "$temp_dir/committed.json" "$temp_dir/current.json"; then
    echo "$sbom_path is stale. Run .github/scripts/sbom/generate-rust.sh and commit the result." >&2
    exit 1
  fi
  echo "$sbom_path is current."
done
