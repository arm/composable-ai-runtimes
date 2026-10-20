# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import pytest

from cairn.perception.v1 import perception_pb2
from perception_service.workflow.issues import ValidationCode
from perception_service.workflow.pipeline import PerceptionPipeline
from perception_service.workflow.validation import validate_pipeline, validate_workflow
from tests.unit.workflow.helpers import StubStageDefinition, inference_stage, workflow

pytestmark = pytest.mark.unit


def test_validate_pipeline_accepts_warnings_and_ordered_stages() -> None:
    warning = perception_pb2.ValidationIssue(
        severity=perception_pb2.VALIDATION_SEVERITY_WARNING,
        code="TEST_WARNING",
        message="warning",
    )
    pipeline = PerceptionPipeline(
        name="pipeline",
        stages=[
            StubStageDefinition(
                "source:camera",
                perception_pb2.RESOLVED_STAGE_ROLE_SOURCE,
            ),
            StubStageDefinition(
                "objects",
                perception_pb2.RESOLVED_STAGE_ROLE_PROCESSING,
                issues=[warning],
            ),
            StubStageDefinition(
                "poses",
                perception_pb2.RESOLVED_STAGE_ROLE_PROCESSING,
            ),
        ],
    )

    valid, issues = validate_pipeline(pipeline)

    assert valid
    assert issues == [warning]
    assert [stage.id for stage in pipeline.resolved_stages] == [
        "source:camera",
        "objects",
        "poses",
    ]


@pytest.mark.parametrize(
    ("stage_valid", "severity"),
    [
        (False, perception_pb2.VALIDATION_SEVERITY_WARNING),
        (True, perception_pb2.VALIDATION_SEVERITY_ERROR),
    ],
)
def test_validate_pipeline_rejects_blocking_stage_results(
    stage_valid: bool,
    severity: perception_pb2.ValidationSeverity,
) -> None:
    issue = perception_pb2.ValidationIssue(
        severity=severity,
        code="TEST_ISSUE",
        message="issue",
    )
    pipeline = PerceptionPipeline(
        name="pipeline",
        stages=[
            StubStageDefinition(
                "source:camera",
                perception_pb2.RESOLVED_STAGE_ROLE_SOURCE,
            ),
            StubStageDefinition(
                "objects",
                perception_pb2.RESOLVED_STAGE_ROLE_PROCESSING,
                valid=stage_valid,
                issues=[issue],
            ),
        ],
    )

    valid, issues = validate_pipeline(pipeline)

    assert not valid
    assert issues == [issue]


def test_validate_pipeline_rejects_duplicate_stage_ids() -> None:
    pipeline = PerceptionPipeline(
        name="pipeline",
        stages=[
            StubStageDefinition(
                "source:camera",
                perception_pb2.RESOLVED_STAGE_ROLE_SOURCE,
            ),
            StubStageDefinition(
                "source:camera",
                perception_pb2.RESOLVED_STAGE_ROLE_PROCESSING,
            ),
        ],
    )

    valid, issues = validate_pipeline(pipeline)

    assert not valid
    assert [issue.code for issue in issues] == [ValidationCode.DUPLICATE_STAGE_ID]


@pytest.mark.parametrize(
    "output",
    [None, perception_pb2.OutputSpec(debug=perception_pb2.DebugOutput())],
)
def test_validate_workflow_accepts_supported_linear_shapes(
    output: perception_pb2.OutputSpec | None,
) -> None:
    valid, issues = validate_workflow(
        workflow(
            stages=[
                inference_stage("objects"),
                inference_stage("poses"),
            ],
            output=output,
        )
    )

    assert valid
    assert issues == []


def test_validate_workflow_reports_required_fields() -> None:
    valid, issues = validate_workflow(perception_pb2.WorkflowSpec())

    assert not valid
    assert [(issue.code, issue.field_path) for issue in issues] == [
        (ValidationCode.WORKFLOW_NAME_REQUIRED, "name"),
        (ValidationCode.SOURCE_REQUIRED, "source"),
        (ValidationCode.INFERENCE_STAGE_REQUIRED, "stages"),
    ]
    assert all(
        issue.severity == perception_pb2.VALIDATION_SEVERITY_ERROR for issue in issues
    )


def test_validate_workflow_reports_required_stage_fields() -> None:
    valid, issues = validate_workflow(
        workflow(stages=[perception_pb2.InferenceStage()])
    )

    assert not valid
    assert [(issue.code, issue.field_path) for issue in issues] == [
        (ValidationCode.STAGE_ID_REQUIRED, "stages[0].id"),
        (ValidationCode.STAGE_NAME_REQUIRED, "stages[0].name"),
        (ValidationCode.MODEL_ID_REQUIRED, "stages[0].model_id"),
    ]


def test_validate_workflow_rejects_duplicate_stage_identity() -> None:
    valid, issues = validate_workflow(
        workflow(
            stages=[
                inference_stage("objects"),
                inference_stage("objects", name="objects"),
            ]
        )
    )

    assert not valid
    assert [(issue.code, issue.field_path, issue.stage_id) for issue in issues] == [
        (ValidationCode.DUPLICATE_STAGE_ID, "stages[1].id", "objects"),
        (ValidationCode.DUPLICATE_STAGE_NAME, "stages[1].name", "objects"),
    ]


def test_validate_workflow_rejects_empty_output() -> None:
    valid, issues = validate_workflow(
        workflow(
            stages=[
                inference_stage("objects"),
                inference_stage("poses"),
            ],
            output=perception_pb2.OutputSpec(),
        )
    )

    assert not valid
    assert [(issue.code, issue.field_path) for issue in issues] == [
        (ValidationCode.OUTPUT_REQUIRED, "output"),
    ]
