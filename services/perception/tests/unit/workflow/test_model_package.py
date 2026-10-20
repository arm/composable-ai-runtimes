# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

import pytest
from loguru import logger

from perception_service.workflow.model_package import create_model_validator
from perception_service.workflow.model_validation import ModelValidator
from tests.helpers import create_model

pytestmark = pytest.mark.unit


@pytest.fixture
def package_validator() -> ModelValidator:
    return create_model_validator(None)


def test_warns_when_json_schema_validation_is_disabled() -> None:
    messages: list[str] = []
    sink = logger.add(messages.append, format="{level}: {message}")
    try:
        create_model_validator(None)
    finally:
        logger.remove(sink)

    assert "WARNING: OPK JSON Schema validation is disabled" in "".join(messages)


def test_validates_complete_model_package(
    tmp_path: Path,
    package_validator: ModelValidator,
) -> None:
    model_path = create_model(tmp_path / "model")

    assert package_validator.validate(model_path) == ()


def test_reports_malformed_descriptor(
    tmp_path: Path,
    package_validator: ModelValidator,
) -> None:
    model_path = create_model(tmp_path / "model")
    descriptor_path = model_path / "opchain.json"
    descriptor_path.write_text("{", encoding="utf-8")

    issues = package_validator.validate(model_path)

    assert len(issues) == 1
    assert issues[0].file == descriptor_path.resolve()
    assert "line 1, column 2" in str(issues[0])


def test_reports_unexpected_descriptor_loading_error(
    tmp_path: Path,
    package_validator: ModelValidator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_path = create_model(tmp_path / "model")
    descriptor_path = model_path / "opchain.json"
    original_read_text = Path.read_text

    def read_text(
        path: Path,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> str:
        if path == descriptor_path:
            raise RuntimeError("unexpected read failure")
        return original_read_text(
            path, encoding=encoding, errors=errors, newline=newline
        )

    monkeypatch.setattr(Path, "read_text", read_text)

    issues = package_validator.validate(model_path)

    assert len(issues) == 1
    assert issues[0].file == descriptor_path.resolve()
    assert issues[0].message == (
        "unexpected error loading descriptor: unexpected read failure"
    )


@pytest.mark.parametrize("descriptor_name", ["opchain.json", "model.json"])
def test_rejects_duplicate_descriptor_keys(
    tmp_path: Path,
    package_validator: ModelValidator,
    descriptor_name: str,
) -> None:
    model_path = create_model(tmp_path / "model")
    descriptor_path = model_path / descriptor_name
    descriptor_path.write_text(
        '{"duplicate": 1, "duplicate": 2}',
        encoding="utf-8",
    )

    issues = package_validator.validate(model_path)

    assert len(issues) == 1
    assert issues[0].file == descriptor_path.resolve()
    assert issues[0].message == "duplicate object key 'duplicate'"


@pytest.mark.parametrize("failure", ["model-reference", "model-file", "inference-op"])
def test_reports_incomplete_package_links(
    tmp_path: Path,
    package_validator: ModelValidator,
    failure: str,
) -> None:
    model_path = create_model(tmp_path / "model")
    if failure == "model-reference":
        opchain_path = model_path / "opchain.json"
        opchain = json.loads(opchain_path.read_text(encoding="utf-8"))
        opchain["ops"][0]["attributes"]["modelDescriptor"] = "other.json"
        opchain_path.write_text(json.dumps(opchain), encoding="utf-8")
        expected = "must reference the package's model.json"
    elif failure == "model-file":
        (model_path / "model.bin").unlink()
        expected = "model file is missing"
    else:
        opchain_path = model_path / "opchain.json"
        opchain = json.loads(opchain_path.read_text(encoding="utf-8"))
        opchain["ops"] = [{"id": "custom/Operation", "attributes": {}}]
        opchain_path.write_text(json.dumps(opchain), encoding="utf-8")
        expected = "at least one inference operation is required"

    issues = package_validator.validate(model_path)

    assert len(issues) == 1
    assert expected in issues[0].message


@pytest.mark.parametrize(
    ("descriptor_name", "field"),
    [
        ("opchain.json", "modelDescriptor"),
        ("model.json", "modelFile"),
    ],
)
def test_reports_invalid_descriptor_paths(
    tmp_path: Path,
    package_validator: ModelValidator,
    descriptor_name: str,
    field: str,
) -> None:
    model_path = create_model(tmp_path / "model")
    descriptor_path = model_path / descriptor_name
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    if field == "modelDescriptor":
        descriptor["ops"][0]["attributes"][field] = "\0"
    else:
        descriptor[field] = "\0"
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")

    issues = package_validator.validate(model_path)

    assert len(issues) == 1
    assert issues[0].location.endswith(field)
    assert "invalid path" in issues[0].message


@pytest.mark.parametrize("invalid_field", ["ops", "modelDescriptor", "modelFile"])
def test_reports_required_integrity_fields_without_schemas(
    tmp_path: Path,
    package_validator: ModelValidator,
    invalid_field: str,
) -> None:
    model_path = create_model(tmp_path / "model")
    if invalid_field == "ops":
        descriptor_path = model_path / "opchain.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        descriptor.pop("ops")
    elif invalid_field == "modelDescriptor":
        descriptor_path = model_path / "opchain.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        descriptor["ops"][0]["attributes"].pop("modelDescriptor")
    else:
        descriptor_path = model_path / "model.json"
        descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
        descriptor.pop("modelFile")
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")

    issues = package_validator.validate(model_path)

    assert len(issues) == 1
    assert issues[0].location.endswith(invalid_field)
