# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Iterable
from dataclasses import dataclass

from cairn.perception.v1.perception_pb2 import (
    OutputSpec,
    ResolvedStage,
    WorkflowSpec,
)
from perception_service.workflow.stage import StageDefinition, StageFactory
from perception_service.workflow.stages.output import FakeSinkStageDefinition
from perception_service.workflow.stages.opk_comm import OpkCommStageDefinition
from perception_service.opk.config import OpkCommEndpoint


class PipelineBuildError(ValueError):
    def __init__(self, message: str, field_path: str) -> None:
        super().__init__(message)
        self.field_path = field_path


class PipelineConstructionError(ValueError):
    pass


def _resolved_stages(
    stages: Iterable[StageDefinition],
) -> tuple[ResolvedStage, ...]:
    return tuple(
        resolved_stage
        for stage in stages
        if (resolved_stage := stage.to_resolved_stage()) is not None
    )


@dataclass(frozen=True)
class CompiledPipeline:
    description: str
    stages: tuple[StageDefinition, ...]

    @property
    def resolved_stages(self) -> tuple[ResolvedStage, ...]:
        return _resolved_stages(self.stages)


def workflow_publishes_events(workflow_spec: WorkflowSpec) -> bool:
    return not workflow_spec.HasField("output_events") or workflow_spec.output_events


@dataclass
class PerceptionPipeline:
    name: str
    stages: list[StageDefinition]

    @property
    def resolved_stages(self) -> list[ResolvedStage]:
        return list(_resolved_stages(self.stages))

    def compile(self) -> CompiledPipeline:
        fragments: list[str] = []

        for stage in self.stages:
            stage_fragments = stage.construct()
            if not stage_fragments:
                raise PipelineConstructionError(
                    f"stage {stage.name!r} did not construct any pipeline fragments"
                )

            for fragment in stage_fragments:
                fragment = fragment.strip()
                if not fragment:
                    raise PipelineConstructionError(
                        f"stage {stage.name!r} constructed an empty pipeline fragment"
                    )
                fragments.append(fragment)

        return CompiledPipeline(
            description=" ! ".join(fragments),
            stages=tuple(self.stages),
        )


class PipelineBuilder:
    def __init__(self, stage_factory: StageFactory) -> None:
        self._stage_factory = stage_factory

    def build_pipeline(
        self,
        workflow_spec: WorkflowSpec,
        opk_comm_endpoint: OpkCommEndpoint | None = None,
    ) -> PerceptionPipeline:
        if workflow_spec.source.WhichOneof("source") != "camera":
            raise PipelineBuildError(
                "workflow must define a supported source",
                "source",
            )

        output_stage = self._create_output_stage(
            workflow_spec.output if workflow_spec.HasField("output") else None
        )

        additive_stages = self._stage_factory.create_additive_stages()
        if opk_comm_endpoint is not None:
            additive_stages = tuple(
                OpkCommStageDefinition(opk_comm_endpoint)
                if isinstance(stage, OpkCommStageDefinition)
                else stage
                for stage in additive_stages
            )

        stages = [
            self._stage_factory.create_stage(workflow_spec.source.camera),
            *(
                self._stage_factory.create_stage(stage)
                for stage in workflow_spec.stages
            ),
            *additive_stages,
            output_stage,
        ]

        return PerceptionPipeline(name=workflow_spec.name, stages=stages)

    def _create_output_stage(self, output: OutputSpec | None) -> StageDefinition:
        if output is None:
            return FakeSinkStageDefinition()

        match output.WhichOneof("output"):
            case "debug":
                return self._stage_factory.create_stage(output.debug)
            case _:
                raise PipelineBuildError(
                    "workflow output must define a supported output",
                    "output",
                )
