# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations


def print_log_group(title: str, log: str) -> None:
    print(f"::group::{title}")
    try:
        print(log, end="")
    finally:
        print("::endgroup::")
