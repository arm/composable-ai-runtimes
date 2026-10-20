# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import pytest
from loguru import logger

from perception_service.workflow.model_validation import ModelIssue
from perception_service.workflow.model_registry import ModelRegistry, RegisteredModel
from tests.helpers import create_model

pytestmark = pytest.mark.unit


class _StubModelValidator:
    @staticmethod
    def validate(model_path: Path) -> tuple[ModelIssue, ...]:
        model_path = model_path.resolve()
        descriptor_path = model_path / "model.json"
        if not descriptor_path.is_file():
            return (
                ModelIssue(
                    descriptor_path,
                    "",
                    "required descriptor is missing",
                ),
            )
        model_file = model_path / "model.bin"
        if not model_file.is_file():
            return (
                ModelIssue(
                    descriptor_path,
                    "/modelFile",
                    f"model file is missing: {model_file}",
                ),
            )
        return ()


VALIDATOR = _StubModelValidator()


def test_model_registry_accepts_no_model_paths() -> None:
    registry = ModelRegistry([], VALIDATOR)

    assert registry.get_model("missing") is None


def test_model_registry_resolves_opchains_from_multiple_model_paths(
    tmp_path: Path,
) -> None:
    first_model = create_model(tmp_path / "first" / "yolov11")
    second_model = create_model(tmp_path / "second" / "mobilenetv2")

    registry = ModelRegistry([first_model, second_model], VALIDATOR)

    assert registry.get_model("yolov11") == RegisteredModel(
        model_id="yolov11",
        opchain_path=first_model.resolve() / "opchain.json",
    )
    assert registry.get_model("mobilenetv2") == RegisteredModel(
        model_id="mobilenetv2",
        opchain_path=second_model.resolve() / "opchain.json",
    )
    assert registry.get_model("missing") is None


def test_model_registry_discovers_models_one_level_below_multiple_roots(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first-root"
    first_model = create_model(first_root / "yolov11")
    create_model(first_root / "nested" / "ignored")
    (first_root / "not-a-model").mkdir()

    second_root = tmp_path / "second-root"
    second_model = create_model(second_root / "mobilenetv2")
    direct_model = create_model(tmp_path / "direct-model")

    registry = ModelRegistry(
        [first_root, direct_model, second_root],
        VALIDATOR,
    )

    assert registry.get_model("yolov11") == RegisteredModel(
        model_id="yolov11",
        opchain_path=first_model.resolve() / "opchain.json",
    )
    assert registry.get_model("mobilenetv2") == RegisteredModel(
        model_id="mobilenetv2",
        opchain_path=second_model.resolve() / "opchain.json",
    )
    assert registry.get_model("direct-model") == RegisteredModel(
        model_id="direct-model",
        opchain_path=direct_model.resolve() / "opchain.json",
    )
    assert registry.get_model("ignored") is None


@pytest.mark.parametrize("invalid_path_kind", ["missing", "file"])
def test_model_registry_rejects_invalid_model_paths(
    tmp_path: Path,
    invalid_path_kind: str,
) -> None:
    model_path = tmp_path / "model"
    if invalid_path_kind == "file":
        model_path.touch()

    with pytest.raises(ValueError, match="mount a model package or parent directory"):
        ModelRegistry([model_path], VALIDATOR)


def test_model_registry_accepts_empty_directory(tmp_path: Path) -> None:
    registry = ModelRegistry([tmp_path], VALIDATOR)

    assert registry.get_model("missing") is None


def test_model_registry_rejects_duplicate_valid_model_ids(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "first"
    create_model(first_root / "model")
    second_model = create_model(tmp_path / "second" / "model")

    with pytest.raises(ValueError, match="registered more than once"):
        ModelRegistry([first_root, second_model], VALIDATOR)


def test_model_registry_skips_invalid_package_and_logs_diagnostic(
    tmp_path: Path,
) -> None:
    model_path = create_model(tmp_path / "broken")
    (model_path / "model.json").unlink()
    messages: list[str] = []
    sink = logger.add(messages.append, format="{message}")
    try:
        registry = ModelRegistry([model_path], VALIDATOR)
    finally:
        logger.remove(sink)

    assert registry.get_model("broken") is None
    log_output = "".join(messages)
    assert "Found model package candidate" in log_output
    assert "Skipping invalid model package" in log_output
    assert str(model_path.resolve() / "model.json") in log_output
    assert "required descriptor is missing" in log_output
    assert "Successfully loaded 0 model(s):" in log_output


def test_model_registry_registers_valid_sibling_of_invalid_package(
    tmp_path: Path,
) -> None:
    root = tmp_path / "models"
    valid = create_model(root / "valid")
    invalid = create_model(root / "invalid")
    (invalid / "model.bin").unlink()

    messages: list[str] = []
    sink = logger.add(messages.append, format="{message}")
    try:
        registry = ModelRegistry([root], VALIDATOR)
    finally:
        logger.remove(sink)

    assert registry.get_model("valid") == RegisteredModel(
        model_id="valid",
        opchain_path=valid.resolve() / "opchain.json",
    )
    assert registry.get_model("invalid") is None
    log_output = "".join(messages)
    assert "Successfully validated model package integrity" in log_output
    assert f"Registered model valid from {valid.resolve()}" in log_output
    assert "Successfully loaded 1 model(s): valid" in log_output
