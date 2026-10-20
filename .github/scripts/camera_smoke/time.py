# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from datetime import UTC, datetime


def get_utc_now() -> str:
    return datetime.now(UTC).isoformat()
