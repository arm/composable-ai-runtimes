#!/bin/sh
# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

set -eu

checks_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
sh "$checks_dir/check-apt.sh"

if [ -n "${VIRTUAL_ENV:-}" ]; then
    python="$VIRTUAL_ENV/bin/python"
    if [ ! -x "$python" ]; then
        printf 'VIRTUAL_ENV declares a missing or non-executable interpreter: %s\n' "$python" >&2
        exit 1
    fi
else
    python=$(command -v python3 || command -v python || true)
fi

if [ -z "$python" ]; then
    printf 'No Python interpreter found; nothing to validate.\n'
    exit 0
fi

# A virtual environment can share its executable with a separate base installation.
base_python=$("$python" -c 'import sys; print(getattr(sys, "_base_executable", sys.executable))')
if [ "$base_python" != "$python" ] && [ -x "$base_python" ]; then
    "$base_python" "$checks_dir/check-python.py"
fi
"$python" "$checks_dir/check-python.py"
