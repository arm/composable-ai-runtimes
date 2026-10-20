# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import Any

import pytest

from perception_service.opk.frame_results import (
    FRAME_RESULTS_ENCODING,
    FrameResultRecord,
    FrameResultsValidationError,
)

pytestmark = pytest.mark.unit


def record(**overrides: Any) -> dict[str, Any]:
    value = {
        "frame_counter": 7,
        "frame_results_encoding": FRAME_RESULTS_ENCODING,
        "frame_results_packet_b64": "RkxXRA==",
    }
    value.update(overrides)
    return value


def test_valid_record_returns_opaque_packet_bytes() -> None:
    result = FrameResultRecord.from_opk_record(record())

    assert result == FrameResultRecord(source_frame_counter=7, packet=b"FLWD")


@pytest.mark.parametrize(
    ("invalid_record", "message"),
    [
        (record(frame_results_encoding="unknown"), "unsupported"),
        (record(frame_results_packet_b64=None), "is required"),
        (record(frame_results_packet_b64="not base64"), "strict Base64"),
        (record(frame_counter=True), "non-negative integer"),
        (record(frame_counter=-1), "non-negative integer"),
    ],
)
def test_invalid_transport_fields_are_rejected(
    invalid_record: dict[str, Any], message: str
) -> None:
    with pytest.raises(FrameResultsValidationError, match=message):
        FrameResultRecord.from_opk_record(invalid_record)
