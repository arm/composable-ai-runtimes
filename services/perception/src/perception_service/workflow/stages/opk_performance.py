# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from cairn.perception.v1.perception_pb2 import (
    RESOLVED_STAGE_ROLE_PROCESSING,
    ValidationIssue,
)
from perception_service.workflow.stage import StageDefinition


class OpkPerformanceStageDefinition(StageDefinition):
    name = "opkperformance"
    role = RESOLVED_STAGE_ROLE_PROCESSING

    def validate(self) -> tuple[bool, list[ValidationIssue]]:
        return True, []

    def construct(self) -> tuple[str, ...]:
        return ("opkperformance",)

    def to_resolved_stage(self) -> None:
        return None
