# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest

from perception_service.workflow.model_validation import (
    InferenceReferenceError,
    Model,
    ModelFileError,
    ModelIssue,
    ModelLoadError,
    ModelValidationStep,
    ModelValidator,
    SchemaValidationError,
    ValidationError,
)

pytestmark = pytest.mark.unit


class _StubLoader:
    def __init__(self, model: Model | ModelLoadError) -> None:
        self._model = model

    def load(self, model_path: Path) -> Model:
        del model_path
        if isinstance(self._model, ModelLoadError):
            raise self._model
        return self._model


class _StubStep:
    def __init__(self, error: ValidationError | None = None) -> None:
        self._error = error

    def validate(self, model: Model) -> None:
        del model
        if self._error is not None:
            raise self._error


@pytest.fixture
def model(tmp_path: Path) -> Model:
    return Model(
        root=tmp_path,
        opchain_path=tmp_path / "opchain.json",
        descriptor_path=tmp_path / "model.json",
        opchain={},
        descriptor={},
    )


def issue(model: Model, message: str) -> ModelIssue:
    return ModelIssue(model.descriptor_path, "", message)


def test_loader_failure_skips_validation_steps(model: Model) -> None:
    expected = issue(model, "could not load model")
    unexpected = issue(model, "validation step should not run")
    loader = _StubLoader(ModelLoadError([expected]))
    step = _StubStep(ModelFileError([unexpected]))

    issues = ModelValidator(loader, [step]).validate(model.root)

    assert issues == (expected,)


def test_schema_failure_stops_remaining_steps(model: Model) -> None:
    expected = issue(model, "invalid schema")
    unexpected = issue(model, "remaining step should not run")
    schema = _StubStep(SchemaValidationError([expected]))
    reference = _StubStep(ModelFileError([unexpected]))

    issues = ModelValidator(_StubLoader(model), [schema, reference]).validate(
        model.root
    )

    assert issues == (expected,)


@pytest.mark.parametrize("error_type", [InferenceReferenceError, ModelFileError])
def test_recoverable_failures_are_aggregated(
    model: Model,
    error_type: type[ValidationError],
) -> None:
    first_issue = issue(model, "first")
    second_issue = issue(model, "second")
    first = _StubStep(error_type([first_issue]))
    second = _StubStep(ModelFileError([second_issue]))

    issues = ModelValidator(_StubLoader(model), [first, second]).validate(model.root)

    assert issues == (first_issue, second_issue)


def test_unknown_validation_error_stops_remaining_steps(model: Model) -> None:
    expected = issue(model, "unknown failure")
    unexpected = issue(model, "remaining step should not run")
    first: ModelValidationStep = _StubStep(ValidationError([expected]))
    second = _StubStep(ModelFileError([unexpected]))

    issues = ModelValidator(_StubLoader(model), [first, second]).validate(model.root)

    assert issues == (expected,)
