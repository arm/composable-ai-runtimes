# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from cairn.perception.v1.perception_pb2 import (
    RESOLVED_STAGE_ROLE_OUTPUT,
    ValidationIssue,
)
from perception_service.opk.config import OpkCommEndpoint
from perception_service.workflow.stage import StageDefinition


class OpkCommStageDefinition(StageDefinition):
    name = "opkcomm"
    role = RESOLVED_STAGE_ROLE_OUTPUT

    def __init__(self, endpoint: OpkCommEndpoint) -> None:
        self._endpoint = endpoint

    def validate(self) -> tuple[bool, list[ValidationIssue]]:
        return True, []

    def construct(self) -> tuple[str, ...]:
        return (f"opkcomm method=websocket ws-port={self._endpoint.port} endpoint=/ws",)

    def to_resolved_stage(self) -> None:
        return None
