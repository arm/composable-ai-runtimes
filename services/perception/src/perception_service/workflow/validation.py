# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Callable, Iterable

from cairn.perception.v1 import perception_pb2
from perception_service.workflow.issues import ValidationCode, validation_error
from perception_service.workflow.pipeline import PerceptionPipeline


type WorkflowCheck = Callable[
    [perception_pb2.WorkflowSpec],
    Iterable[perception_pb2.ValidationIssue],
]


def _check_workflow_name(
    workflow: perception_pb2.WorkflowSpec,
) -> Iterable[perception_pb2.ValidationIssue]:
    if not workflow.name.strip():
        yield validation_error(
            ValidationCode.WORKFLOW_NAME_REQUIRED,
            "workflow name is required",
            "name",
        )


def _check_source(
    workflow: perception_pb2.WorkflowSpec,
) -> Iterable[perception_pb2.ValidationIssue]:
    if workflow.source.WhichOneof("source") != "camera":
        yield validation_error(
            ValidationCode.SOURCE_REQUIRED,
            "workflow must define a supported source",
            "source",
        )


def _check_inference_stages(
    workflow: perception_pb2.WorkflowSpec,
) -> Iterable[perception_pb2.ValidationIssue]:
    if not workflow.stages:
        yield validation_error(
            ValidationCode.INFERENCE_STAGE_REQUIRED,
            "workflow must define at least one inference stage",
            "stages",
        )


def _check_stage_identity(
    workflow: perception_pb2.WorkflowSpec,
) -> Iterable[perception_pb2.ValidationIssue]:
    stage_ids: set[str] = set()
    stage_names: set[str] = set()

    for index, stage in enumerate(workflow.stages):
        stage_path = f"stages[{index}]"
        stage_id = stage.id

        if not stage_id.strip():
            yield validation_error(
                ValidationCode.STAGE_ID_REQUIRED,
                "stage ID is required",
                f"{stage_path}.id",
            )
        elif stage_id in stage_ids:
            yield validation_error(
                ValidationCode.DUPLICATE_STAGE_ID,
                f"stage ID {stage_id!r} is already used",
                f"{stage_path}.id",
                stage_id,
            )

        if not stage.name.strip():
            yield validation_error(
                ValidationCode.STAGE_NAME_REQUIRED,
                "stage name is required",
                f"{stage_path}.name",
                stage_id or None,
            )
        elif stage.name in stage_names:
            yield validation_error(
                ValidationCode.DUPLICATE_STAGE_NAME,
                f"stage name {stage.name!r} is already used",
                f"{stage_path}.name",
                stage_id or None,
            )

        if stage_id:
            stage_ids.add(stage_id)
        if stage.name:
            stage_names.add(stage.name)


def _check_stage_models(
    workflow: perception_pb2.WorkflowSpec,
) -> Iterable[perception_pb2.ValidationIssue]:
    for index, stage in enumerate(workflow.stages):
        if not stage.model_id.strip():
            yield validation_error(
                ValidationCode.MODEL_ID_REQUIRED,
                "model ID is required",
                f"stages[{index}].model_id",
                stage.id or None,
            )


def _check_output(
    workflow: perception_pb2.WorkflowSpec,
) -> Iterable[perception_pb2.ValidationIssue]:
    if workflow.HasField("output") and workflow.output.WhichOneof("output") != "debug":
        yield validation_error(
            ValidationCode.OUTPUT_REQUIRED,
            "workflow output must define a supported output",
            "output",
        )


WORKFLOW_CHECKS: tuple[WorkflowCheck, ...] = (
    _check_workflow_name,
    _check_source,
    _check_inference_stages,
    _check_stage_identity,
    _check_stage_models,
    _check_output,
)


def validate_workflow(
    workflow: perception_pb2.WorkflowSpec,
) -> tuple[bool, list[perception_pb2.ValidationIssue]]:
    issues = [issue for check in WORKFLOW_CHECKS for issue in check(workflow)]
    valid = not any(
        issue.severity == perception_pb2.VALIDATION_SEVERITY_ERROR for issue in issues
    )
    return valid, issues


def validate_pipeline(
    pipeline: PerceptionPipeline,
) -> tuple[bool, list[perception_pb2.ValidationIssue]]:
    issues: list[perception_pb2.ValidationIssue] = []
    resolved_stage_ids: set[str] = set()
    valid = True

    for stage in pipeline.stages:
        stage_valid, stage_issues = stage.validate()
        issues.extend(stage_issues)
        if not stage_valid or any(
            issue.severity == perception_pb2.VALIDATION_SEVERITY_ERROR
            for issue in stage_issues
        ):
            valid = False

        resolved_stage = stage.to_resolved_stage()
        if resolved_stage is None:
            continue

        if resolved_stage.id in resolved_stage_ids:
            issues.append(
                validation_error(
                    ValidationCode.DUPLICATE_STAGE_ID,
                    f"resolved stage ID {resolved_stage.id!r} is already used",
                    "stages",
                    resolved_stage.id,
                )
            )
            valid = False

        resolved_stage_ids.add(resolved_stage.id)

    return valid, issues
