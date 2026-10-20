# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import pytest

from cairn.perception.v1 import perception_pb2
from perception_service.opk.config import OpkCommEndpoint
from perception_service.workflow.pipeline import (
    PerceptionPipeline,
    PipelineBuilder,
    PipelineBuildError,
    PipelineConstructionError,
    workflow_publishes_events,
)
from perception_service.workflow.stages.opk_comm import OpkCommStageDefinition
from perception_service.workflow.stages.opk_performance import (
    OpkPerformanceStageDefinition,
)
from tests.unit.workflow.helpers import (
    StubStageDefinition,
    create_stage_dependencies,
    create_stage_factory,
    inference_stage,
    workflow,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("value", [None, True, False])
def test_workflow_event_publication_respects_optional_flag(value: bool | None) -> None:
    spec = perception_pb2.WorkflowSpec()
    if value is not None:
        spec.output_events = value

    assert workflow_publishes_events(spec) is (value is not False)


def test_construct_pipeline_appends_fakesink_when_no_output_is_requested() -> None:
    pipeline = PipelineBuilder(
        create_stage_factory(create_stage_dependencies())
    ).build_pipeline(workflow())

    compiled = pipeline.compile()

    assert compiled.description == "source ! caps ! objects ! fakesink sync=false"
    assert [stage.id for stage in compiled.resolved_stages] == [
        "source:camera",
        "objects",
    ]
    assert compiled.stages == tuple(pipeline.stages)


def test_construct_pipeline_joins_trimmed_fragments_in_stage_order() -> None:
    pipeline = PipelineBuilder(
        create_stage_factory(create_stage_dependencies())
    ).build_pipeline(
        workflow(output=perception_pb2.OutputSpec(debug=perception_pb2.DebugOutput()))
    )

    compiled = pipeline.compile()

    assert compiled.description == "source ! caps ! objects ! sink"
    assert [stage.id for stage in compiled.resolved_stages] == [
        "source:camera",
        "objects",
        "output:debug",
    ]
    assert compiled.stages == tuple(pipeline.stages)


def test_construct_pipeline_inserts_registered_additive_stages() -> None:
    dependencies = create_stage_dependencies(
        OpkCommEndpoint(host="127.0.0.2", port=7002)
    )
    pipeline = PipelineBuilder(
        create_stage_factory(dependencies, include_additive_stages=True)
    ).build_pipeline(workflow())

    compiled = pipeline.compile()

    assert compiled.description == (
        "source ! caps ! objects ! opkperformance ! "
        "opkcomm method=websocket ws-port=7002 endpoint=/ws ! "
        "fakesink sync=false"
    )
    assert [
        type(stage)
        for stage in pipeline.stages
        if isinstance(
            stage,
            (OpkPerformanceStageDefinition, OpkCommStageDefinition),
        )
    ] == [OpkPerformanceStageDefinition, OpkCommStageDefinition]
    assert [stage.id for stage in compiled.resolved_stages] == [
        "source:camera",
        "objects",
    ]


def test_construct_pipeline_adds_each_registered_extension_once() -> None:
    dependencies = create_stage_dependencies(OpkCommEndpoint())
    pipeline = PipelineBuilder(
        create_stage_factory(dependencies, include_additive_stages=True)
    ).build_pipeline(
        workflow(stages=[inference_stage("objects"), inference_stage("poses")])
    )

    compiled = pipeline.compile()

    assert compiled.description.count("opkperformance") == 1
    assert compiled.description.count("opkcomm") == 1


def test_result_output_uses_reserved_endpoint() -> None:
    builder = PipelineBuilder(
        create_stage_factory(
            create_stage_dependencies(),
            include_additive_stages=True,
        )
    )

    compiled = builder.build_pipeline(
        workflow(),
        OpkCommEndpoint(port=7010),
    ).compile()

    assert "ws-port=7010" in compiled.description


@pytest.mark.parametrize("fragments", [(), ("   ",)])
def test_construct_pipeline_rejects_empty_fragments(
    fragments: tuple[str, ...],
) -> None:
    pipeline = PerceptionPipeline(
        name="pipeline",
        stages=[
            StubStageDefinition(
                "source",
                perception_pb2.RESOLVED_STAGE_ROLE_SOURCE,
                fragments=fragments,
            )
        ],
    )

    with pytest.raises(PipelineConstructionError):
        pipeline.compile()


def test_pipeline_builder_preserves_workflow_and_stage_order() -> None:
    pipeline = PipelineBuilder(
        create_stage_factory(create_stage_dependencies())
    ).build_pipeline(
        workflow(
            stages=[inference_stage("objects"), inference_stage("poses")],
            output=perception_pb2.OutputSpec(debug=perception_pb2.DebugOutput()),
        )
    )

    assert pipeline.name == "workflow"
    assert [stage.id for stage in pipeline.resolved_stages] == [
        "source:camera",
        "objects",
        "poses",
        "output:debug",
    ]


@pytest.mark.parametrize(
    ("invalid_workflow", "field_path"),
    [
        (perception_pb2.WorkflowSpec(name="missing-source"), "source"),
        (
            workflow(output=perception_pb2.OutputSpec()),
            "output",
        ),
    ],
)
def test_pipeline_builder_rejects_missing_stage_variants(
    invalid_workflow: perception_pb2.WorkflowSpec,
    field_path: str,
) -> None:
    with pytest.raises(PipelineBuildError) as error:
        PipelineBuilder(
            create_stage_factory(create_stage_dependencies())
        ).build_pipeline(invalid_workflow)

    assert error.value.field_path == field_path
