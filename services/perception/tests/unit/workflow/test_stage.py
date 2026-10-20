# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from dataclasses import FrozenInstanceError

import pytest

from cairn.perception.v1 import perception_pb2
from perception_service.opk.config import OpkCommEndpoint
from perception_service.workflow.model_registry import ModelRegistry
from perception_service.workflow.stage import (
    StageDefinition,
    StageDependencies,
    StageFactory,
    UnsupportedStageError,
)
from tests.helpers import MODEL_VALIDATOR
from tests.unit.workflow.helpers import (
    StubStageDefinition,
    create_stage_dependencies,
)

pytestmark = pytest.mark.unit


def test_stage_factory_rejects_duplicate_and_unsupported_registrations() -> None:
    dependencies = create_stage_dependencies()
    factory = StageFactory(dependencies)

    def constructor(
        _: perception_pb2.StreamConfiguration,
        _dependencies: StageDependencies,
    ) -> StageDefinition:
        return StubStageDefinition(
            "source",
            perception_pb2.RESOLVED_STAGE_ROLE_SOURCE,
        )

    factory.register_stage(perception_pb2.StreamConfiguration, constructor)

    with pytest.raises(ValueError, match="stage already registered"):
        factory.register_stage(perception_pb2.StreamConfiguration, constructor)

    with pytest.raises(UnsupportedStageError):
        factory.create_stage(perception_pb2.InferenceStage())


def test_stage_factory_creates_registered_additive_stages_in_order() -> None:
    factory = StageFactory(create_stage_dependencies())
    factory.register_additive_stage(
        lambda _dependencies: StubStageDefinition(
            "performance",
            perception_pb2.RESOLVED_STAGE_ROLE_PROCESSING,
            fragments=("opkperformance",),
        )
    )
    factory.register_additive_stage(
        lambda _dependencies: StubStageDefinition(
            "comm",
            perception_pb2.RESOLVED_STAGE_ROLE_OUTPUT,
            fragments=("opkcomm",),
        )
    )

    first = factory.create_additive_stages()
    second = factory.create_additive_stages()

    assert [stage.construct() for stage in first] == [
        ("opkperformance",),
        ("opkcomm",),
    ]
    assert first[0] is not second[0]


def test_stage_dependencies_are_immutable_and_required() -> None:
    model_registry = ModelRegistry([], MODEL_VALIDATOR)
    endpoint = OpkCommEndpoint(host="127.0.0.2", port=7002)
    dependencies = StageDependencies(
        model_registry=model_registry,
        opk_comm_endpoint=endpoint,
    )

    assert dependencies.model_registry is model_registry
    assert dependencies.opk_comm_endpoint is endpoint
    with pytest.raises(FrozenInstanceError):
        setattr(dependencies, "opk_comm_endpoint", OpkCommEndpoint())
