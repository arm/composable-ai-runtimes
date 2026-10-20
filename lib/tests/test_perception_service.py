# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for the Python Perception API."""

import asyncio

import pytest
from cairn import (
    FrameRate,
    Resolution,
    StreamConfiguration,
    StreamFormat,
    perception,
)
from cairn.perception import (
    DebugOutput,
    DeploymentValidationError,
    PerceptionDeploymentError,
    PerceptionError,
    PerceptionService,
    PerceptionWorkflow,
)


def test_perception_submodule_is_exported() -> None:
    assert perception.PerceptionService is PerceptionService


def test_perception_errors_follow_deployment_hierarchy() -> None:
    assert issubclass(DeploymentValidationError, PerceptionError)
    assert issubclass(PerceptionDeploymentError, PerceptionError)
    assert issubclass(DeploymentValidationError, PerceptionDeploymentError)


def test_deployment_validation_error_has_no_issues_by_default() -> None:
    error = DeploymentValidationError("failed")

    assert error.issues is None


def test_workflow_builds_inference_stages() -> None:
    camera_configuration = StreamConfiguration(
        "opaque/pipewire:target",
        7,
        StreamFormat(Resolution(1920, 1080), "NV12", FrameRate(30000, 1001)),
    )
    workflow = PerceptionWorkflow(
        "front-door", source_configuration=camera_configuration
    )

    first_stage = workflow.infer("objects", "yolov11")
    second_stage = workflow.infer("faces", "retinaface")
    output = DebugOutput(http_port=9999)
    workflow.output(output)

    with pytest.raises(TypeError):
        PerceptionWorkflow("front-door", camera_configuration.target)
    assert (output.http_port, output.ws_port, output.ctrl_port) == (9999, 0, 0)
    assert (first_stage.id, first_stage.name) == ("inference-1", "objects")
    assert (second_stage.id, second_stage.name) == ("inference-2", "faces")


def test_connect_rejects_invalid_endpoint() -> None:
    async def connect() -> None:
        with pytest.raises(
            PerceptionError,
            match="failed to connect to perception service at",
        ):
            await PerceptionService.connect("http://[::1")

    asyncio.run(connect())
