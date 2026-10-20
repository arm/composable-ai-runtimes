#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

# Run from the repository root with an output directory and cargo-about arguments.
set -euo pipefail

notices="${1:?Usage: generate.sh OUTPUT_DIRECTORY CARGO_ABOUT_ARGUMENTS...}"
shift
source .github/scripts/rust-notices/toolchain.env
export RUSTUP_TOOLCHAIN

mkdir -p "$notices"
cargo about generate --locked --fail "$@" \
  --config .github/scripts/rust-notices/about.toml \
  .github/scripts/rust-notices/about.hbs -o "$notices/THIRD_PARTY_NOTICES.txt"
if grep -Eq '<copyright holders>|<year> <owner>' "$notices/THIRD_PARTY_NOTICES.txt"; then
  echo "::error::Placeholder attribution: update about.toml."
  exit 1
fi
rust_docs="$(rustc --print sysroot)/share/doc/rust"
cp "$rust_docs/COPYRIGHT-library.html" "$notices/"
cp -R "$rust_docs/licenses" "$notices/"
