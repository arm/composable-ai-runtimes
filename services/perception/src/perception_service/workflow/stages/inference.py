# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from loguru import logger

from cairn.perception.v1.perception_pb2 import (
    RESOLVED_STAGE_ROLE_PROCESSING,
    InferenceStage,
    ResolvedStage,
    ValidationIssue,
)
from perception_service.gstreamer.values import contains_nul, serialize_gstreamer_string
from perception_service.workflow.issues import ValidationCode, validation_error
from perception_service.workflow.model_registry import ModelRegistry
from perception_service.workflow.stage import StageConstructionError, StageDefinition


class InferenceStageDefinition(StageDefinition):
    name = "inference"
    role = RESOLVED_STAGE_ROLE_PROCESSING
    controllable = True

    def __init__(
        self,
        source_definition: InferenceStage,
        model_registry: ModelRegistry,
    ) -> None:
        self._source_definition = source_definition
        self._model_registry = model_registry

    def validate(self) -> tuple[bool, list[ValidationIssue]]:
        stage = self._source_definition
        issues: list[ValidationIssue] = []

        if stage.id and contains_nul(stage.id):
            issues.append(
                validation_error(
                    ValidationCode.STAGE_ID_INVALID,
                    "stage ID must not contain NUL characters",
                    "stages.id",
                    stage.id,
                )
            )

        if stage.model_id and self._model_registry.get_model(stage.model_id) is None:
            issues.append(
                validation_error(
                    ValidationCode.MODEL_NOT_FOUND,
                    f"model {stage.model_id!r} is not installed",
                    "stages.model_id",
                    stage.id or None,
                )
            )

        return not issues, issues

    def construct(self) -> tuple[str, ...]:
        stage = self._source_definition
        if contains_nul(stage.id):
            raise StageConstructionError(
                "stage ID must not contain NUL characters",
                field_path="stages.id",
                stage_id=stage.id or None,
            )

        model = self._model_registry.get_model(stage.model_id)
        if model is None:
            raise StageConstructionError(
                f"model {stage.model_id!r} is not installed",
                field_path="stages.model_id",
                stage_id=stage.id or None,
            )
        try:
            stage_id = serialize_gstreamer_string(stage.id)
            serialized_opchain_path = serialize_gstreamer_string(
                str(model.opchain_path)
            )
        except ValueError as error:
            raise StageConstructionError(
                "could not serialize inference stage configuration",
                field_path="stages",
                stage_id=stage.id or None,
            ) from error

        logger.debug(
            "Constructing inference stage {} with model {} from {}",
            stage.id,
            stage.model_id,
            model.opchain_path,
        )
        return (
            f"opkinfer name={stage_id} infer-id={stage_id} "
            f"opchain-path={serialized_opchain_path} active=true",
        )

    def to_resolved_stage(self) -> ResolvedStage:
        return ResolvedStage(
            id=self._source_definition.id,
            name=self._source_definition.name,
            role=self.role,
            controllable=self.controllable,
            model_id=self._source_definition.model_id,
        )
