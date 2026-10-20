# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from pathlib import Path

from loguru import logger

from perception_service.workflow.model_schema import JsonSchemaValidator
from perception_service.workflow.model_validation import (
    Document,
    DocumentValue,
    InferenceReferenceValidator,
    Model,
    ModelFileValidator,
    ModelIssue,
    ModelLoadError,
    ModelValidationStep,
    ModelValidator,
)


class _DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(
    pairs: list[tuple[str, DocumentValue]],
) -> dict[str, DocumentValue]:
    result: dict[str, DocumentValue] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeyError(f"duplicate object key {key!r}")
        result[key] = value
    return result


class JsonModelLoader:
    def load(self, model_path: Path) -> Model:
        model_root = model_path.resolve()
        opchain_path = model_root / "opchain.json"
        descriptor_path = model_root / "model.json"
        opchain, issues = self._load_descriptor(opchain_path)
        descriptor, descriptor_issues = self._load_descriptor(descriptor_path)
        issues.extend(descriptor_issues)
        if opchain is None or descriptor is None:
            raise ModelLoadError(issues)

        return Model(
            root=model_root,
            opchain_path=opchain_path,
            descriptor_path=descriptor_path,
            opchain=opchain,
            descriptor=descriptor,
        )

    @staticmethod
    def _load_descriptor(
        path: Path,
    ) -> tuple[Document | None, list[ModelIssue]]:
        try:
            if not path.is_file():
                return None, [ModelIssue(path, "", "required descriptor is missing")]
            content = path.read_text(encoding="utf-8")
            document = json.loads(content, object_pairs_hook=_reject_duplicate_keys)
        except json.JSONDecodeError as error:
            return None, [
                ModelIssue(
                    path,
                    f"line {error.lineno}, column {error.colno}",
                    error.msg,
                )
            ]
        except _DuplicateKeyError as error:
            return None, [ModelIssue(path, "", str(error))]
        except (OSError, UnicodeError) as error:
            return None, [ModelIssue(path, "", f"could not read descriptor: {error}")]
        except Exception as error:
            logger.opt(exception=error).error(
                "Unexpected error while loading model descriptor {}", path
            )
            return None, [
                ModelIssue(path, "", f"unexpected error loading descriptor: {error}")
            ]

        if not isinstance(document, dict):
            return None, [ModelIssue(path, "", "descriptor must be a JSON object")]
        return document, []


def create_model_validator(schema_root: Path | None) -> ModelValidator:
    if schema_root is None:
        logger.warning("OPK JSON Schema validation is disabled")
    steps: list[ModelValidationStep] = (
        [JsonSchemaValidator(schema_root)] if schema_root is not None else []
    )
    return ModelValidator(
        JsonModelLoader(), steps + [InferenceReferenceValidator(), ModelFileValidator()]
    )
