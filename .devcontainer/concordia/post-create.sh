#!/usr/bin/env bash
set -euo pipefail

cd /workspaces/cairn-sdk/services/concordia
/opt/venv/bin/uv sync --active --extra dev
