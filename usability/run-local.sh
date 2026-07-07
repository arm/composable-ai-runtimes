#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "OPENAI_API_KEY is not set"
  exit 1
fi

uv run --with pyyaml==6.0.2 --with requests==2.32.3 \
  python usability/run_framework.py \
  --results-dir usability/results \
  --history usability/history/history.json
