# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from cairn.perception.v1 import perception_pb2
from perception_service.opk.config import OpkCommEndpoint
from perception_service.workflow.model_registry import ModelRegistry
from perception_service.workflow.stage import (
    StageDefinition,
    StageDependencies,
    StageFactory,
)
from perception_service.workflow.stages.opk_comm import OpkCommStageDefinition
from perception_service.workflow.stages.opk_performance import (
    OpkPerformanceStageDefinition,
)
from tests.helpers import MODEL_VALIDATOR


class StubStageDefinition(StageDefinition):
    name = "stub"
    role = perception_pb2.RESOLVED_STAGE_ROLE_UNSPECIFIED

    def __init__(
        self,
        stage_id: str,
        role: perception_pb2.ResolvedStageRole,
        *,
        fragments: tuple[str, ...] = ("stub",),
        valid: bool = True,
        issues: list[perception_pb2.ValidationIssue] | None = None,
    ) -> None:
        self._stage_id = stage_id
        self._role = role
        self._fragments = fragments
        self._valid = valid
        self._issues = issues or []

    def validate(self) -> tuple[bool, list[perception_pb2.ValidationIssue]]:
        return self._valid, self._issues

    def construct(self) -> tuple[str, ...]:
        return self._fragments

    def to_resolved_stage(self) -> perception_pb2.ResolvedStage:
        return perception_pb2.ResolvedStage(
            id=self._stage_id,
            name=self._stage_id,
            role=self._role,
        )


def inference_stage(
    stage_id: str = "objects",
    *,
    name: str | None = None,
    model_id: str = "yolov11",
) -> perception_pb2.InferenceStage:
    return perception_pb2.InferenceStage(
        id=stage_id,
        name=name if name is not None else stage_id,
        model_id=model_id,
    )


def workflow(
    *,
    stages: list[perception_pb2.InferenceStage] | None = None,
    output: perception_pb2.OutputSpec | None = None,
) -> perception_pb2.WorkflowSpec:
    return perception_pb2.WorkflowSpec(
        name="workflow",
        source=perception_pb2.SourceSpec(camera=perception_pb2.StreamConfiguration()),
        stages=stages if stages is not None else [inference_stage()],
        output=output,
    )


def create_stage_dependencies(
    opk_comm_endpoint: OpkCommEndpoint = OpkCommEndpoint(),
) -> StageDependencies:
    return StageDependencies(
        model_registry=ModelRegistry([], MODEL_VALIDATOR),
        opk_comm_endpoint=opk_comm_endpoint,
    )


def create_stage_factory(
    dependencies: StageDependencies,
    *,
    include_additive_stages: bool = False,
) -> StageFactory:
    factory = StageFactory(dependencies)
    factory.register_stage(
        perception_pb2.StreamConfiguration,
        lambda _, _dependencies: StubStageDefinition(
            "source:camera",
            perception_pb2.RESOLVED_STAGE_ROLE_SOURCE,
            fragments=(" source ", " caps "),
        ),
    )
    factory.register_stage(
        perception_pb2.InferenceStage,
        lambda definition, _dependencies: StubStageDefinition(
            definition.id,
            perception_pb2.RESOLVED_STAGE_ROLE_PROCESSING,
            fragments=(f" {definition.id} ",),
        ),
    )
    factory.register_stage(
        perception_pb2.DebugOutput,
        lambda _, _dependencies: StubStageDefinition(
            "output:debug",
            perception_pb2.RESOLVED_STAGE_ROLE_OUTPUT,
            fragments=(" sink ",),
        ),
    )
    if include_additive_stages:
        factory.register_additive_stage(lambda _: OpkPerformanceStageDefinition())
        factory.register_additive_stage(
            lambda dependencies: OpkCommStageDefinition(
                dependencies.opk_comm_endpoint,
            )
        )
    return factory
