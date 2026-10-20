# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import pytest

from perception_service.gstreamer.runtime_policy import validate_runtime_limits

pytestmark = pytest.mark.unit


def test_validate_runtime_limits_accepts_positive_values() -> None:
    validate_runtime_limits(
        state_change_timeout_seconds=0.2,
        max_pipelines=1,
    )


@pytest.mark.parametrize(
    ("state_timeout", "max_pipelines", "message"),
    [
        (0, 1, "state change timeout"),
        (1, 0, "maximum pipelines"),
    ],
)
def test_validate_runtime_limits_rejects_non_positive_values(
    state_timeout: float,
    max_pipelines: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        validate_runtime_limits(
            state_timeout,
            max_pipelines,
        )
