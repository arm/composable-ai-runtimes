# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import gi
import pytest

gi.require_version("Gst", "1.0")
from gi.repository import Gst as GstRuntime  # noqa: E402

from perception_service.errors import FailedPreconditionError, NotFoundError  # noqa: E402
from perception_service.gstreamer.runtime import (  # noqa: E402
    ManagedPipeline,
)

from .runtime_test_support import (  # noqa: E402
    create_runtime,
)

pytestmark = pytest.mark.integration


def test_set_inference_stage_active_updates_an_opkinfer_element() -> None:
    with create_runtime() as runtime:
        session_id = "pipeline-session"
        stage = MagicMock()
        pipeline = MagicMock(spec=GstRuntime.Pipeline)
        pipeline.get_by_name.return_value = stage
        stage.get_factory.return_value.get_name.return_value = "opkinfer"
        stage.get_property.return_value = False

        runtime._pipelines[session_id] = ManagedPipeline(
            pipeline=pipeline,
            bus=MagicMock(),
            bus_handler_id=1,
            session_id=session_id,
            event_sink=lambda _event: None,
        )
        active = runtime.set_inference_stage_active(session_id, "objects", False)
        runtime._pipelines.pop(session_id)

    assert not active
    pipeline.get_by_name.assert_called_once_with("objects")
    stage.set_property.assert_called_once_with("active", False)
    stage.get_property.assert_called_once_with("active")


def test_set_inference_stage_active_rejects_an_unknown_pipeline() -> None:
    with create_runtime() as runtime:
        with pytest.raises(NotFoundError, match="missing-session"):
            runtime.set_inference_stage_active("missing-session", "objects", False)


def test_set_inference_stage_active_rejects_an_unknown_stage() -> None:
    class Pipeline:
        def get_by_name(self, stage_name: str) -> None:
            return None

    with create_runtime() as runtime:
        session_id = "pipeline-session"
        runtime._pipelines[session_id] = ManagedPipeline(
            pipeline=cast(GstRuntime.Pipeline, Pipeline()),
            bus=MagicMock(),
            bus_handler_id=1,
            session_id=session_id,
            event_sink=lambda _event: None,
        )
        with pytest.raises(NotFoundError, match="objects"):
            runtime.set_inference_stage_active(session_id, "objects", False)
        runtime._pipelines.pop(session_id)


def test_set_inference_stage_active_rejects_a_non_opkinfer_element() -> None:
    class Factory:
        def get_name(self) -> str:
            return "fakesink"

    class Stage:
        def get_factory(self) -> Factory:
            return Factory()

    class Pipeline:
        def get_by_name(self, stage_name: str) -> Stage:
            return Stage()

    with create_runtime() as runtime:
        session_id = "pipeline-session"
        runtime._pipelines[session_id] = ManagedPipeline(
            pipeline=cast(GstRuntime.Pipeline, Pipeline()),
            bus=MagicMock(),
            bus_handler_id=1,
            session_id=session_id,
            event_sink=lambda _event: None,
        )
        with pytest.raises(FailedPreconditionError, match="objects"):
            runtime.set_inference_stage_active(session_id, "objects", False)
        runtime._pipelines.pop(session_id)
