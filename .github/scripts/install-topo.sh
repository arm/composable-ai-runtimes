#!/usr/bin/env bash
set -euo pipefail

TOPO_VERSION="${1:?usage: install-topo.sh <version>}"
INSTALL_DIR="${2:-$HOME/.local/bin}"
INSTALL_SCRIPT_URL="https://raw.githubusercontent.com/arm/topo/refs/heads/main/scripts/install.sh"

tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT

curl -fsSL "$INSTALL_SCRIPT_URL" -o "$tmp_dir/install-topo.sh"
sh "$tmp_dir/install-topo.sh" --version "$TOPO_VERSION" --path "$INSTALL_DIR"
"$INSTALL_DIR/topo" --version
