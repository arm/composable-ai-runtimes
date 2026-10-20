# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError as JsonSchemaDefinitionError
from jsonschema.protocols import Validator as JsonSchemaProtocol
from referencing import Registry, Resource
from referencing.exceptions import CannotDetermineSpecification, Unresolvable
from referencing.jsonschema import SchemaRegistry, SchemaResource

from perception_service.workflow.model_validation import (
    Document,
    DocumentValue,
    Model,
    ModelIssue,
    SchemaValidationError,
)


MODEL_SCHEMA_ID = "urn:arm:opk:schema:model-descriptor:v1"
OPCHAIN_SCHEMA_ID = "urn:arm:opk:schema:opchain-descriptor:v1"
MODEL_SCHEMA_FILE = "model.schema.json"
OPCHAIN_SCHEMA_FILE = "opchain.schema.json"
SUPPORTING_SCHEMA_FILES = (
    "opchain/common.schema.json",
    "opchain/op.schema.json",
    "opchain/ops/generic-image-preprocess.schema.json",
    "opchain/ops/generic-postprocess.schema.json",
    "opchain/ops/inference-controller.schema.json",
    "opchain/ops/inference.schema.json",
    "opchain/ops/python-script.schema.json",
)


class SchemaConfigurationError(ValueError):
    """The OPK schema bundle is missing, unreadable, or internally invalid."""


def _json_pointer(path: Iterable[object]) -> str:
    return "".join(
        f"/{str(component).replace('~', '~0').replace('/', '~1')}" for component in path
    )


class JsonSchemaValidator:
    def __init__(self, schema_root: Path) -> None:
        self._schema_root = schema_root
        self._validators: tuple[JsonSchemaProtocol, JsonSchemaProtocol] | None = None

    def _load_validators(
        self,
    ) -> tuple[JsonSchemaProtocol, JsonSchemaProtocol]:
        if self._validators is not None:
            return self._validators

        schema_root = self._schema_root.resolve()
        if not schema_root.is_dir():
            raise SchemaConfigurationError(
                f"OPK model schema path is not a directory: {schema_root}"
            )

        model_schema = self._load_root_schema(
            schema_root / MODEL_SCHEMA_FILE,
            MODEL_SCHEMA_ID,
        )
        opchain_schema = self._load_root_schema(
            schema_root / OPCHAIN_SCHEMA_FILE,
            OPCHAIN_SCHEMA_ID,
        )
        registry = self._load_supporting_registry(schema_root)
        model_validator = Draft202012Validator(model_schema, registry=registry)
        opchain_validator = Draft202012Validator(
            opchain_schema,
            registry=registry,
        )
        self._validators = (model_validator, opchain_validator)
        return self._validators

    @classmethod
    def _load_root_schema(cls, path: Path, expected_id: str) -> Document:
        schema_id, schema, _ = cls._load_schema_resource(path)
        if schema_id != expected_id:
            raise SchemaConfigurationError(
                f"OPK root schema has unexpected $id: {path}: "
                f"expected {expected_id!r}, found {schema_id!r}"
            )
        return schema

    @classmethod
    def _load_supporting_registry(
        cls,
        schema_root: Path,
    ) -> SchemaRegistry:
        resources: dict[str, SchemaResource] = {}
        root_ids = {MODEL_SCHEMA_ID, OPCHAIN_SCHEMA_ID}
        for relative_path in SUPPORTING_SCHEMA_FILES:
            schema_id, _, resource = cls._load_schema_resource(
                schema_root / relative_path
            )
            if schema_id in root_ids or schema_id in resources:
                raise SchemaConfigurationError(
                    f"OPK schema $id is duplicated: {schema_id}"
                )
            resources[schema_id] = resource
        registry: SchemaRegistry = Registry()
        return registry.with_resources(resources.items())

    @classmethod
    def _load_schema_resource(
        cls,
        path: Path,
    ) -> tuple[str, Document, SchemaResource]:
        schema = cls._load_schema(path)
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str) or not schema_id:
            raise SchemaConfigurationError(f"OPK schema has no non-empty $id: {path}")
        try:
            Draft202012Validator.check_schema(schema)
            resource = Resource.from_contents(schema)
        except (
            CannotDetermineSpecification,
            JsonSchemaDefinitionError,
            ValueError,
        ) as error:
            raise SchemaConfigurationError(
                f"OPK schema is invalid: {path}: {error}"
            ) from error
        return schema_id, schema, resource

    @staticmethod
    def _load_schema(path: Path) -> Document:
        try:
            content = path.read_text(encoding="utf-8")
            schema = json.loads(content)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
        ) as error:
            raise SchemaConfigurationError(
                f"could not read OPK schema {path}: {error}"
            ) from error
        if not isinstance(schema, dict):
            raise SchemaConfigurationError(f"OPK schema is not a JSON object: {path}")
        return schema

    @staticmethod
    def _collect_validation_issues(
        path: Path,
        document: Mapping[str, DocumentValue],
        validator: JsonSchemaProtocol,
    ) -> list[ModelIssue]:
        try:
            errors = validator.iter_errors(document)
            return [
                ModelIssue(path, _json_pointer(error.absolute_path), error.message)
                for error in errors
            ]
        except Unresolvable as error:
            raise SchemaConfigurationError(
                f"OPK schema reference could not be resolved: {error}"
            ) from error

    def validate(self, model: Model) -> None:
        model_validator, opchain_validator = self._load_validators()
        issues = self._collect_validation_issues(
            model.opchain_path,
            model.opchain,
            opchain_validator,
        )
        issues.extend(
            self._collect_validation_issues(
                model.descriptor_path,
                model.descriptor,
                model_validator,
            )
        )
        if issues:
            raise SchemaValidationError(issues)
