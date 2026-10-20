# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from typing import ClassVar, Final

from cairn.perception.v1.perception_pb2 import (
    RESOLVED_STAGE_ROLE_OUTPUT,
    DebugOutput,
    DebugPorts,
    ResolvedStage,
    ValidationIssue,
)
from perception_service.workflow.issues import ValidationCode, validation_error
from perception_service.workflow.stage import StageConstructionError, StageDefinition

DEFAULT_DEBUG_HTTP_PORT: Final = 9999
DEFAULT_DEBUG_WS_PORT: Final = 8000
DEFAULT_DEBUG_CTRL_PORT: Final = 8001
MAX_NETWORK_PORT: Final = 65535


def _resolve_debug_ports(definition: DebugOutput) -> DebugPorts:
    return DebugPorts(
        http_port=definition.http_port or DEFAULT_DEBUG_HTTP_PORT,
        ws_port=definition.ws_port or DEFAULT_DEBUG_WS_PORT,
        ctrl_port=definition.ctrl_port or DEFAULT_DEBUG_CTRL_PORT,
    )


class FakeSinkStageDefinition(StageDefinition):
    static_id: ClassVar[str] = "output:fakesink"
    name = "fakesink"
    role = RESOLVED_STAGE_ROLE_OUTPUT

    def validate(self) -> tuple[bool, list[ValidationIssue]]:
        return True, []

    def construct(self) -> tuple[str, ...]:
        return ("fakesink sync=false",)

    def to_resolved_stage(self) -> None:
        return None


class OpkSinkStageDefinition(StageDefinition):
    static_id: ClassVar[str] = "output:debug"
    name = "opksink"
    role = RESOLVED_STAGE_ROLE_OUTPUT

    def __init__(self, source_definition: DebugOutput):
        self._debug_ports = _resolve_debug_ports(source_definition)

    @property
    def debug_ports(self) -> DebugPorts:
        return DebugPorts(
            http_port=self._debug_ports.http_port,
            ws_port=self._debug_ports.ws_port,
            ctrl_port=self._debug_ports.ctrl_port,
        )

    def validate(self) -> tuple[bool, list[ValidationIssue]]:
        issues: list[ValidationIssue] = []
        ports = self._debug_ports

        for field_name, value in (
            ("http_port", ports.http_port),
            ("ws_port", ports.ws_port),
            ("ctrl_port", ports.ctrl_port),
        ):
            if not 1 <= value <= MAX_NETWORK_PORT:
                issues.append(
                    validation_error(
                        ValidationCode.DEBUG_PORT_INVALID,
                        f"debug {field_name} must be between 1 and {MAX_NETWORK_PORT}",
                        f"output.debug.{field_name}",
                        self.static_id,
                    )
                )

        if len({ports.http_port, ports.ws_port, ports.ctrl_port}) != 3:
            issues.append(
                validation_error(
                    ValidationCode.DEBUG_PORTS_DUPLICATE,
                    "debug HTTP, WebSocket, and control ports must be distinct",
                    "output.debug",
                    self.static_id,
                )
            )

        return not issues, issues

    def construct(self) -> tuple[str, ...]:
        valid, issues = self.validate()
        if not valid:
            issue = issues[0]
            raise StageConstructionError(
                issue.message,
                field_path=issue.field_path,
                stage_id=self.static_id,
            )

        ports = self._debug_ports
        return (
            "opkosd enabled=true",
            f"opksink http-port={ports.http_port} ws-port={ports.ws_port} "
            f"ctrl-port={ports.ctrl_port}",
        )

    def to_resolved_stage(self) -> ResolvedStage:
        return ResolvedStage(
            id=self.static_id,
            name=self.name,
            role=self.role,
            controllable=self.controllable,
        )
