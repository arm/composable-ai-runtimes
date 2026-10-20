#!/usr/bin/env bash
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  build-essential \
  libcairo2-dev \
  libgirepository-2.0-dev \
  pkg-config
rm -rf /var/lib/apt/lists/*

/usr/local/bin/python -m pip install --no-cache-dir uv==0.11.32
cd /workspaces/cairn-sdk/services/perception
/usr/local/bin/uv sync --locked
