# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import json
import shutil
from pathlib import Path

import pytest

from perception_service.workflow.model_package import JsonModelLoader
from perception_service.workflow.model_schema import (
    JsonSchemaValidator,
    SchemaConfigurationError,
)
from perception_service.workflow.model_validation import SchemaValidationError
from tests.helpers import create_model

pytestmark = pytest.mark.integration

OPK_SCHEMA_PATH = Path("/opt/opk/share/opk/schemas/json/v1")


@pytest.fixture
def schema_root() -> Path:
    assert OPK_SCHEMA_PATH.is_dir(), (
        f"installed OPK schema bundle is missing: {OPK_SCHEMA_PATH}"
    )
    return OPK_SCHEMA_PATH


@pytest.fixture
def mutable_schema_root(tmp_path: Path, schema_root: Path) -> Path:
    destination = tmp_path / "schemas"
    shutil.copytree(schema_root, destination)
    return destination


def test_matches_descriptors_by_fixed_schema_id(
    tmp_path: Path,
    schema_root: Path,
) -> None:
    model_path = create_model(tmp_path / "model")
    descriptor_path = model_path / "model.json"
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    descriptor["version"] = 2
    descriptor_path.write_text(json.dumps(descriptor), encoding="utf-8")

    with pytest.raises(SchemaValidationError) as raised:
        JsonSchemaValidator(schema_root).validate(JsonModelLoader().load(model_path))

    assert len(raised.value.issues) == 1
    assert raised.value.issues[0].file == descriptor_path.resolve()
    assert raised.value.issues[0].location == "/version"


def test_resolves_references_from_installed_schema_bundle(
    tmp_path: Path,
    schema_root: Path,
) -> None:
    model_path = create_model(tmp_path / "model")

    JsonSchemaValidator(schema_root).validate(JsonModelLoader().load(model_path))


def test_rejects_root_with_unexpected_schema_id(
    tmp_path: Path,
    mutable_schema_root: Path,
) -> None:
    schema_path = mutable_schema_root / "model.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["$id"] = "urn:test:other"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    model_path = create_model(tmp_path / "model")

    with pytest.raises(
        SchemaConfigurationError,
        match=r"root schema has unexpected \$id.*model.schema.json",
    ):
        JsonSchemaValidator(mutable_schema_root).validate(
            JsonModelLoader().load(model_path)
        )


def test_rejects_supporting_resource_that_uses_root_id(
    tmp_path: Path,
    mutable_schema_root: Path,
) -> None:
    root_schema = json.loads(
        (mutable_schema_root / "model.schema.json").read_text(encoding="utf-8")
    )
    schema_path = mutable_schema_root / "opchain/common.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["$id"] = root_schema["$id"]
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    model_path = create_model(tmp_path / "model")

    with pytest.raises(SchemaConfigurationError, match=r"schema \$id is duplicated"):
        JsonSchemaValidator(mutable_schema_root).validate(
            JsonModelLoader().load(model_path)
        )


def test_rejects_missing_supporting_resource(
    tmp_path: Path,
    mutable_schema_root: Path,
) -> None:
    schema_path = mutable_schema_root / "opchain/ops/inference.schema.json"
    schema_path.unlink()
    model_path = create_model(tmp_path / "model")

    with pytest.raises(
        SchemaConfigurationError,
        match="could not read OPK schema.*inference.schema.json",
    ):
        JsonSchemaValidator(mutable_schema_root).validate(
            JsonModelLoader().load(model_path)
        )


def test_rejects_unresolvable_schema_reference(
    tmp_path: Path,
    mutable_schema_root: Path,
) -> None:
    schema_path = mutable_schema_root / "opchain.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema["$ref"] = "urn:test:missing"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    model_path = create_model(tmp_path / "model")

    with pytest.raises(
        SchemaConfigurationError,
        match="schema reference could not be resolved",
    ):
        JsonSchemaValidator(mutable_schema_root).validate(
            JsonModelLoader().load(model_path)
        )


def test_rejects_schema_without_determinable_specification(
    tmp_path: Path,
    mutable_schema_root: Path,
) -> None:
    schema_path = mutable_schema_root / "model.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    schema.pop("$schema")
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    model_path = create_model(tmp_path / "model")

    with pytest.raises(
        SchemaConfigurationError,
        match="OPK schema is invalid",
    ):
        JsonSchemaValidator(mutable_schema_root).validate(
            JsonModelLoader().load(model_path)
        )


def test_does_not_load_schemas_until_validation(tmp_path: Path) -> None:
    JsonSchemaValidator(tmp_path / "missing-schemas")
