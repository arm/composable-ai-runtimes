# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Any, Mapping, Self

FRAME_RESULTS_ENCODING = "perception-frame-results+base64"


class FrameResultsValidationError(ValueError):
    pass


@dataclass(frozen=True)
class FrameResultRecord:
    source_frame_counter: int
    packet: bytes

    @classmethod
    def from_opk_record(cls, record: Mapping[str, Any]) -> Self:
        encoding = record.get("frame_results_encoding")
        if encoding != FRAME_RESULTS_ENCODING:
            raise FrameResultsValidationError(
                f"unsupported frame_results_encoding: {encoding!r}"
            )

        frame_counter = record.get("frame_counter")
        if type(frame_counter) is not int or frame_counter < 0:
            raise FrameResultsValidationError(
                "frame_counter must be a non-negative integer"
            )

        encoded_packet = record.get("frame_results_packet_b64")
        if not isinstance(encoded_packet, str) or not encoded_packet:
            raise FrameResultsValidationError("frame_results_packet_b64 is required")
        try:
            packet = base64.b64decode(encoded_packet, validate=True)
        except (binascii.Error, ValueError) as error:
            raise FrameResultsValidationError(
                "frame_results_packet_b64 is not strict Base64"
            ) from error

        return cls(source_frame_counter=frame_counter, packet=packet)
