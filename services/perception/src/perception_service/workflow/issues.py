# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from enum import StrEnum, unique

from cairn.perception.v1 import perception_pb2


@unique
class ValidationCode(StrEnum):
    WORKFLOW_NAME_REQUIRED = "WORKFLOW_NAME_REQUIRED"
    SOURCE_REQUIRED = "SOURCE_REQUIRED"
    PIPEWIRE_TARGET_REQUIRED = "PIPEWIRE_TARGET_REQUIRED"
    PIPEWIRE_TARGET_INVALID = "PIPEWIRE_TARGET_INVALID"
    CAMERA_DIMENSION_INVALID = "CAMERA_DIMENSION_INVALID"
    CAMERA_FRAME_RATE_INVALID = "CAMERA_FRAME_RATE_INVALID"
    CAMERA_FORMAT_REQUIRED = "CAMERA_FORMAT_REQUIRED"
    UNSUPPORTED_CAMERA_FORMAT = "UNSUPPORTED_CAMERA_FORMAT"
    UNKNOWN_CAMERA_FORMAT = "UNKNOWN_CAMERA_FORMAT"
    INFERENCE_STAGE_REQUIRED = "INFERENCE_STAGE_REQUIRED"
    STAGE_ID_REQUIRED = "STAGE_ID_REQUIRED"
    STAGE_ID_INVALID = "STAGE_ID_INVALID"
    DUPLICATE_STAGE_ID = "DUPLICATE_STAGE_ID"
    STAGE_NAME_REQUIRED = "STAGE_NAME_REQUIRED"
    DUPLICATE_STAGE_NAME = "DUPLICATE_STAGE_NAME"
    MODEL_ID_REQUIRED = "MODEL_ID_REQUIRED"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    OUTPUT_REQUIRED = "OUTPUT_REQUIRED"
    DEBUG_PORT_INVALID = "DEBUG_PORT_INVALID"
    DEBUG_PORTS_DUPLICATE = "DEBUG_PORTS_DUPLICATE"
    INVALID_WORKFLOW_STRUCTURE = "INVALID_WORKFLOW_STRUCTURE"
    UNSUPPORTED_STAGE = "UNSUPPORTED_STAGE"
    PIPELINE_CONSTRUCTION_FAILED = "PIPELINE_CONSTRUCTION_FAILED"


def validation_error(
    code: ValidationCode,
    message: str,
    field_path: str,
    stage_id: str | None = None,
) -> perception_pb2.ValidationIssue:
    issue = perception_pb2.ValidationIssue(
        severity=perception_pb2.VALIDATION_SEVERITY_ERROR,
        code=code.value,
        message=message,
        field_path=field_path,
    )
    if stage_id is not None:
        issue.stage_id = stage_id
    return issue
