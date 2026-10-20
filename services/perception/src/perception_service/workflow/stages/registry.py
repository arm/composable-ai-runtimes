# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from cairn.perception.v1.perception_pb2 import (
    StreamConfiguration,
    DebugOutput,
    InferenceStage,
)
from perception_service.workflow.stage import StageDependencies, StageFactory
from perception_service.workflow.stages.inference import InferenceStageDefinition
from perception_service.workflow.stages.output import OpkSinkStageDefinition
from perception_service.workflow.stages.opk_comm import OpkCommStageDefinition
from perception_service.workflow.stages.opk_performance import (
    OpkPerformanceStageDefinition,
)
from perception_service.workflow.stages.source import CameraSourceDefinition


def create_stage_factory(dependencies: StageDependencies) -> StageFactory:
    stage_factory = StageFactory(dependencies)
    stage_factory.register_stage(
        StreamConfiguration,
        lambda definition, _: CameraSourceDefinition(definition),
    )
    stage_factory.register_stage(
        InferenceStage,
        lambda definition, dependencies: InferenceStageDefinition(
            definition,
            dependencies.model_registry,
        ),
    )
    stage_factory.register_additive_stage(lambda _: OpkPerformanceStageDefinition())
    stage_factory.register_additive_stage(
        lambda dependencies: OpkCommStageDefinition(
            dependencies.opk_comm_endpoint,
        )
    )
    stage_factory.register_stage(
        DebugOutput,
        lambda definition, _: OpkSinkStageDefinition(definition),
    )
    return stage_factory
