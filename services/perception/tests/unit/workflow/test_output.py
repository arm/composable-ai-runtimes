# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import pytest

from cairn.perception.v1 import perception_pb2
from perception_service.opk.config import OpkCommEndpoint
from perception_service.workflow.issues import ValidationCode
from perception_service.workflow.model_registry import ModelRegistry
from perception_service.workflow.stage import StageConstructionError, StageDependencies
from perception_service.workflow.stages.output import OpkSinkStageDefinition
from perception_service.workflow.stages.registry import create_stage_factory
from tests.helpers import MODEL_VALIDATOR

pytestmark = pytest.mark.unit


def test_opksink_stage_constructs_default_debug_output() -> None:
    definition = OpkSinkStageDefinition(perception_pb2.DebugOutput())

    assert definition.validate() == (True, [])
    assert definition.debug_ports == perception_pb2.DebugPorts(
        http_port=9999,
        ws_port=8000,
        ctrl_port=8001,
    )
    assert definition.construct() == (
        "opkosd enabled=true",
        "opksink http-port=9999 ws-port=8000 ctrl-port=8001",
    )
    assert definition.to_resolved_stage() == perception_pb2.ResolvedStage(
        id="output:debug",
        name="opksink",
        role=perception_pb2.RESOLVED_STAGE_ROLE_OUTPUT,
    )


def test_opksink_stage_constructs_requested_ports() -> None:
    definition = OpkSinkStageDefinition(
        perception_pb2.DebugOutput(
            http_port=10000,
            ws_port=10001,
            ctrl_port=10002,
        )
    )

    assert definition.validate() == (True, [])
    assert definition.debug_ports == perception_pb2.DebugPorts(
        http_port=10000,
        ws_port=10001,
        ctrl_port=10002,
    )
    assert definition.construct() == (
        "opkosd enabled=true",
        "opksink http-port=10000 ws-port=10001 ctrl-port=10002",
    )


@pytest.mark.parametrize("field_name", ["http_port", "ws_port", "ctrl_port"])
def test_opksink_stage_rejects_ports_outside_network_range(
    field_name: str,
) -> None:
    definition = OpkSinkStageDefinition(
        perception_pb2.DebugOutput(**{field_name: 65536})
    )

    valid, issues = definition.validate()

    assert not valid
    assert [issue.code for issue in issues] == [ValidationCode.DEBUG_PORT_INVALID]
    assert issues[0].field_path == f"output.debug.{field_name}"
    assert issues[0].stage_id == "output:debug"

    with pytest.raises(StageConstructionError) as error:
        definition.construct()

    assert error.value.field_path == f"output.debug.{field_name}"
    assert error.value.stage_id == "output:debug"


@pytest.mark.parametrize(
    "output",
    [
        perception_pb2.DebugOutput(
            http_port=8000,
            ws_port=8000,
            ctrl_port=8001,
        ),
        perception_pb2.DebugOutput(
            ws_port=9999,
        ),
    ],
)
def test_opksink_stage_rejects_duplicate_resolved_ports(
    output: perception_pb2.DebugOutput,
) -> None:
    definition = OpkSinkStageDefinition(output)

    valid, issues = definition.validate()

    assert not valid
    assert [issue.code for issue in issues] == [ValidationCode.DEBUG_PORTS_DUPLICATE]
    assert issues[0].field_path == "output.debug"

    with pytest.raises(StageConstructionError, match="must be distinct"):
        definition.construct()


def test_stage_factory_registers_opksink_output() -> None:
    definition = create_stage_factory(
        StageDependencies(
            model_registry=ModelRegistry([], MODEL_VALIDATOR),
            opk_comm_endpoint=OpkCommEndpoint(),
        )
    ).create_stage(perception_pb2.DebugOutput())

    assert isinstance(definition, OpkSinkStageDefinition)
