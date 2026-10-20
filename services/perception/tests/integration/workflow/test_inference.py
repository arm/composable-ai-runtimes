# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

from cairn.perception.v1 import perception_pb2
from perception_service.opk.config import OpkCommEndpoint
from perception_service.workflow.issues import ValidationCode
from perception_service.workflow.model_registry import ModelRegistry
from perception_service.workflow.stage import (
    StageConstructionError,
    StageDependencies,
)
from perception_service.workflow.stages.inference import InferenceStageDefinition
from perception_service.workflow.stages.opk_comm import OpkCommStageDefinition
from perception_service.workflow.stages.opk_performance import (
    OpkPerformanceStageDefinition,
)
from perception_service.workflow.stages.registry import create_stage_factory
from tests.helpers import create_model


class _AcceptingModelValidator:
    @staticmethod
    def validate(model_path: Path) -> tuple[()]:
        del model_path
        return ()


VALIDATOR = _AcceptingModelValidator()

pytestmark = pytest.mark.integration


def test_inference_stage_constructs_opkinfer_for_registered_model(
    tmp_path: Path,
) -> None:
    model_path = create_model(tmp_path / "yolov11")
    definition = InferenceStageDefinition(
        inference_stage(),
        ModelRegistry([model_path], VALIDATOR),
    )

    assert definition.validate() == (True, [])
    assert definition.construct() == (
        "opkinfer name=objects infer-id=objects "
        f"opchain-path={model_path.resolve() / 'opchain.json'} active=true",
    )


def test_inference_stage_rejects_unknown_model() -> None:
    definition = InferenceStageDefinition(
        inference_stage(), ModelRegistry([], VALIDATOR)
    )

    valid, issues = definition.validate()

    assert not valid
    assert len(issues) == 1
    assert issues[0].code == ValidationCode.MODEL_NOT_FOUND
    assert issues[0].field_path == "stages.model_id"
    assert issues[0].stage_id == "objects"

    with pytest.raises(StageConstructionError, match="is not installed"):
        definition.construct()


def test_inference_stage_rejects_invalid_stage_id(
    tmp_path: Path,
) -> None:
    model_path = create_model(tmp_path / "yolov11")
    stage = inference_stage()
    stage.id = "objects\x00suffix"
    definition = InferenceStageDefinition(stage, ModelRegistry([model_path], VALIDATOR))

    valid, issues = definition.validate()

    assert not valid
    assert [issue.code for issue in issues] == [ValidationCode.STAGE_ID_INVALID]
    assert issues[0].field_path == "stages.id"

    with pytest.raises(StageConstructionError, match="must not contain NUL"):
        definition.construct()


def test_stage_factory_injects_shared_model_registry(tmp_path: Path) -> None:
    model_path = create_model(tmp_path / "yolov11")
    registry = ModelRegistry([model_path], VALIDATOR)
    dependencies = StageDependencies(
        model_registry=registry,
        opk_comm_endpoint=OpkCommEndpoint(),
    )
    factory = create_stage_factory(dependencies)
    stage = inference_stage()

    first = factory.create_stage(stage)
    second = factory.create_stage(stage)

    assert isinstance(first, InferenceStageDefinition)
    assert isinstance(second, InferenceStageDefinition)
    assert first is not second
    assert first.construct() == second.construct()


def test_stage_factory_injects_opkcomm_endpoint_into_additive_stages() -> None:
    dependencies = StageDependencies(
        model_registry=ModelRegistry([], VALIDATOR),
        opk_comm_endpoint=OpkCommEndpoint(host="127.0.0.2", port=7002),
    )
    factory = create_stage_factory(dependencies)

    stages = factory.create_additive_stages()

    assert [type(stage) for stage in stages] == [
        OpkPerformanceStageDefinition,
        OpkCommStageDefinition,
    ]
    assert [stage.construct() for stage in stages] == [
        ("opkperformance",),
        ("opkcomm method=websocket ws-port=7002 endpoint=/ws",),
    ]


def inference_stage() -> perception_pb2.InferenceStage:
    return perception_pb2.InferenceStage(
        id="objects",
        name="objects",
        model_id="yolov11",
    )
