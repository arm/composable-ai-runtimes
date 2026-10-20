# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar

from cairn.perception.v1.perception_pb2 import (
    StreamConfiguration,
    DebugOutput,
    InferenceStage,
    ResolvedStage,
    ResolvedStageRole,
    ValidationIssue,
)
from perception_service.opk.config import OpkCommEndpoint
from perception_service.workflow.model_registry import ModelRegistry


type InputStage = InferenceStage | StreamConfiguration | DebugOutput


@dataclass(frozen=True)
class StageDependencies:
    model_registry: ModelRegistry
    opk_comm_endpoint: OpkCommEndpoint


class UnsupportedStageError(LookupError):
    def __init__(self, stage: InputStage) -> None:
        self.stage_type = type(stage)
        super().__init__(f"no stage registered for {self.stage_type.__name__}")


class StageConstructionError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        field_path: str,
        stage_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.field_path = field_path
        self.stage_id = stage_id


class StageDefinition(ABC):
    name: ClassVar[str]
    role: ClassVar[ResolvedStageRole]
    controllable: ClassVar[bool] = False

    @abstractmethod
    def validate(self) -> tuple[bool, list[ValidationIssue]]:
        """Validates the stage configuration."""
        raise NotImplementedError("Subclasses must implement the validate method.")

    @abstractmethod
    def construct(self) -> tuple[str, ...]:
        """Return ordered GStreamer fragments.

        Raise StageConstructionError for client-correctable configuration failures.
        """
        raise NotImplementedError("Subclasses must implement the construct method.")

    @abstractmethod
    def to_resolved_stage(self) -> ResolvedStage | None:
        """Return exposed stage metadata, or None for an internal stage."""
        raise NotImplementedError(
            "Subclasses must implement the to_resolved_stage method."
        )


class StageFactory:
    def __init__(self, dependencies: StageDependencies) -> None:
        self._dependencies = dependencies
        self._stages: dict[
            type[InputStage], Callable[[InputStage, StageDependencies], StageDefinition]
        ] = {}
        self._additive_stages: list[Callable[[StageDependencies], StageDefinition]] = []

    def register_stage[T: InputStage](
        self,
        input_type: type[T],
        constructor: Callable[[T, StageDependencies], StageDefinition],
    ) -> None:
        """Register a constructor for an exact protobuf stage type."""
        if input_type in self._stages:
            raise ValueError(f"stage already registered for {input_type.__name__}")

        def create(
            definition: InputStage,
            dependencies: StageDependencies,
        ) -> StageDefinition:
            if not isinstance(definition, input_type):
                raise TypeError(
                    f"expected {input_type.__name__}, got {type(definition).__name__}"
                )
            return constructor(definition, dependencies)

        self._stages[input_type] = create

    def register_additive_stage(
        self,
        constructor: Callable[[StageDependencies], StageDefinition],
    ) -> None:
        """Register a service-owned stage for additive pipeline construction."""
        self._additive_stages.append(constructor)

    def create_stage(self, stage: InputStage) -> StageDefinition:
        constructor = self._stages.get(type(stage))
        if constructor is None:
            raise UnsupportedStageError(stage)
        return constructor(stage, self._dependencies)

    def create_additive_stages(self) -> tuple[StageDefinition, ...]:
        return tuple(
            constructor(self._dependencies) for constructor in self._additive_stages
        )
