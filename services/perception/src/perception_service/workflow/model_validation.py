# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


type DocumentValue = (
    None | bool | int | float | str | list[DocumentValue] | dict[str, DocumentValue]
)
type Document = Mapping[str, DocumentValue]


@dataclass(frozen=True)
class Model:
    """Loaded model package descriptors and their resolved paths."""

    root: Path
    opchain_path: Path
    descriptor_path: Path
    opchain: Document
    descriptor: Document


@dataclass(frozen=True, order=True)
class ModelIssue:
    """A validation issue associated with a model package location."""

    file: Path
    location: str
    message: str

    def __str__(self) -> str:
        location = f":{self.location}" if self.location else ""
        return f"{self.file}{location}: {self.message}"


class ValidationError(Exception):
    """Base error containing one or more model validation issues."""

    def __init__(self, issues: Sequence[ModelIssue]) -> None:
        self.issues = tuple(issues)
        super().__init__("\n".join(str(issue) for issue in self.issues))


class ModelLoadError(ValidationError):
    """Raised when model package descriptors cannot be loaded."""


class SchemaValidationError(ValidationError):
    """Raised when model descriptors violate their JSON Schemas."""


class InferenceReferenceError(ValidationError):
    """Raised when inference operations contain invalid model references."""


class ModelFileError(ValidationError):
    """Raised when a model descriptor references an invalid model file."""


class ModelLoader(Protocol):
    """Load model package descriptors for validation."""

    def load(self, model_path: Path) -> Model: ...


class ModelValidationStep(Protocol):
    """Validate one aspect of a loaded model package."""

    def validate(self, model: Model) -> None: ...


class ModelValidation(Protocol):
    """Validate a model package path and return discovered issues."""

    def validate(self, model_path: Path) -> tuple[ModelIssue, ...]: ...


class ModelValidator:
    """Load a model package and orchestrate its validation steps."""

    def __init__(
        self,
        loader: ModelLoader,
        steps: Sequence[ModelValidationStep],
    ) -> None:
        self._loader = loader
        self._steps = tuple(steps)

    def validate(self, model_path: Path) -> tuple[ModelIssue, ...]:
        try:
            model = self._loader.load(model_path)
        except ModelLoadError as error:
            return tuple(sorted(error.issues))

        issues: list[ModelIssue] = []
        for step in self._steps:
            try:
                step.validate(model)
            except ValidationError as error:
                issues.extend(error.issues)
                if not isinstance(error, (InferenceReferenceError, ModelFileError)):
                    break

        return tuple(sorted(issues))


class InferenceReferenceValidator:
    """Validate inference operations and their descriptor references."""

    def validate(self, model: Model) -> None:
        issues: list[ModelIssue] = []
        inference_references: list[tuple[int, str]] = []
        inference_operation_found = False
        operations = model.opchain.get("ops")
        if not isinstance(operations, list):
            raise InferenceReferenceError(
                [ModelIssue(model.opchain_path, "/ops", "operations must be a list")]
            )
        for index, operation in enumerate(operations):
            if not isinstance(operation, dict):
                continue
            operation_id = operation.get("id")
            if not isinstance(operation_id, str) or not operation_id.endswith(
                "/Inference"
            ):
                continue
            inference_operation_found = True
            attributes = operation.get("attributes")
            reference = (
                attributes.get("modelDescriptor")
                if isinstance(attributes, dict)
                else None
            )
            if not isinstance(reference, str) or not reference:
                issues.append(
                    ModelIssue(
                        model.opchain_path,
                        f"/ops/{index}/attributes/modelDescriptor",
                        "inference operation must reference model.json",
                    )
                )
                continue
            inference_references.append((index, reference))

        if not inference_operation_found:
            issues.append(
                ModelIssue(
                    model.opchain_path,
                    "/ops",
                    "at least one inference operation is required",
                )
            )

        canonical_descriptor = model.descriptor_path.resolve()
        for index, reference in inference_references:
            referenced_path = Path(reference)
            if not referenced_path.is_absolute():
                referenced_path = model.root / referenced_path
            try:
                resolved_reference = referenced_path.resolve()
            except (OSError, RuntimeError, ValueError) as error:
                issues.append(
                    ModelIssue(
                        model.opchain_path,
                        f"/ops/{index}/attributes/modelDescriptor",
                        f"inference operation references an invalid path: {error}",
                    )
                )
                continue
            if resolved_reference != canonical_descriptor:
                issues.append(
                    ModelIssue(
                        model.opchain_path,
                        f"/ops/{index}/attributes/modelDescriptor",
                        "inference operation must reference the package's model.json",
                    )
                )

        if issues:
            raise InferenceReferenceError(issues)


class ModelFileValidator:
    """Validate the model file referenced by a model descriptor."""

    def validate(self, model: Model) -> None:
        model_file_value = model.descriptor.get("modelFile")
        if not isinstance(model_file_value, str) or not model_file_value:
            raise ModelFileError(
                [
                    ModelIssue(
                        model.descriptor_path,
                        "/modelFile",
                        "modelFile must be a non-empty string",
                    )
                ]
            )

        model_file = Path(model_file_value)
        if not model_file.is_absolute():
            model_file = model.root / model_file
        try:
            resolved_model_file = model_file.resolve()
            is_model_file = resolved_model_file.is_file()
        except (OSError, RuntimeError, ValueError) as error:
            raise ModelFileError(
                [
                    ModelIssue(
                        model.descriptor_path,
                        "/modelFile",
                        f"modelFile references an invalid path: {error}",
                    )
                ]
            ) from error
        if not is_model_file:
            raise ModelFileError(
                [
                    ModelIssue(
                        model.descriptor_path,
                        "/modelFile",
                        "model file is missing or is not a regular file: "
                        f"{resolved_model_file}",
                    )
                ]
            )
