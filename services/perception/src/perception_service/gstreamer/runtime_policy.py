# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

def validate_runtime_limits(
    state_change_timeout_seconds: float,
    max_pipelines: int,
) -> None:
    if state_change_timeout_seconds <= 0:
        raise ValueError("state change timeout must be positive")
    if max_pipelines <= 0:
        raise ValueError("maximum pipelines must be positive")
