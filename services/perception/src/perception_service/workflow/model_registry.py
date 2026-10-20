# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from loguru import logger
from perception_service.workflow.model_validation import ModelValidation


@dataclass(frozen=True)
class RegisteredModel:
    model_id: str
    opchain_path: Path


class ModelRegistry:
    def __init__(
        self,
        model_paths: Iterable[Path],
        validator: ModelValidation,
    ) -> None:
        models: dict[str, RegisteredModel] = {}
        configured_paths = tuple(model_paths)

        for configured_path in configured_paths:
            for model_path in self._discover_model_paths(configured_path):
                logger.debug("Found model package candidate: {}", model_path)
                issues = validator.validate(model_path)
                if issues:
                    logger.bind(model_path=str(model_path)).error(
                        "Skipping invalid model package {}:\n{}",
                        model_path,
                        "\n".join(f"- {issue}" for issue in issues),
                    )
                    continue

                logger.debug(
                    "Successfully validated model package integrity: {}",
                    model_path,
                )
                model_id = model_path.name
                if model_id in models:
                    raise ValueError(
                        f"model ID is registered more than once: {model_id!r}"
                    )

                models[model_id] = RegisteredModel(
                    model_id=model_id,
                    opchain_path=model_path / "opchain.json",
                )
                logger.debug("Registered model {} from {}", model_id, model_path)

        self._models = MappingProxyType(models)
        logger.info("Successfully loaded {} model(s): {}", len(models), ", ".join(sorted(models)))

    @staticmethod
    def _discover_model_paths(configured_path: Path) -> tuple[Path, ...]:
        configured_path = configured_path.resolve()
        if not configured_path.is_dir():
            raise ValueError(
                f"model path is not a directory: {configured_path}; mount a model "
                "package or parent directory and select it with --model-path"
            )

        descriptor_names = ("opchain.json", "model.json")
        if any((configured_path / name).is_file() for name in descriptor_names):
            return (configured_path,)

        model_paths = tuple(
            child.resolve()
            for child in sorted(configured_path.iterdir())
            if child.is_dir()
            and any((child / name).is_file() for name in descriptor_names)
        )
        if not model_paths:
            logger.warning(
                "Model path contains no model packages: {}; continuing without models "
                "from this path. Mount a model package containing opchain.json and "
                "model.json here or select another path with --model-path",
                configured_path,
            )

        return model_paths

    def get_model(self, model_id: str) -> RegisteredModel | None:
        return self._models.get(model_id)
