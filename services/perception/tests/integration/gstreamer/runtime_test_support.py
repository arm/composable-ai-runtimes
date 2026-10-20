# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from unittest.mock import MagicMock

import gi

from perception_service.pipeline_types import PipelineEventSink

gi.require_version("Gst", "1.0")
from gi.repository import Gst as GstRuntime  # noqa: E402

from perception_service.gstreamer.glib_dispatcher import GLibTaskDispatcher  # noqa: E402
from perception_service.gstreamer.runtime import (  # noqa: E402
    GStreamerRuntime,
    ManagedPipeline,
)

PLAYING_PIPELINE = "videotestsrc is-live=true ! fakesink sync=false"


def create_runtime(
    command_queue_timeout_seconds: float = 10,
    state_change_timeout_seconds: float = 5,
    max_pipelines: int = 16,
) -> GStreamerRuntime:
    return GStreamerRuntime(
        GLibTaskDispatcher(command_queue_timeout_seconds),
        state_change_timeout_seconds,
        max_pipelines,
    )


def mock_pipeline_with_failed_first_stop() -> MagicMock:
    bus = MagicMock()
    bus.connect.return_value = 1
    pipeline = MagicMock()
    pipeline.get_bus.return_value = bus
    pipeline.set_state.side_effect = [
        GstRuntime.StateChangeReturn.SUCCESS,
        GstRuntime.StateChangeReturn.SUCCESS,
        GstRuntime.StateChangeReturn.SUCCESS,
    ]
    pipeline.get_state.side_effect = [
        (
            GstRuntime.StateChangeReturn.SUCCESS,
            GstRuntime.State.PLAYING,
            GstRuntime.State.VOID_PENDING,
        ),
        (
            GstRuntime.StateChangeReturn.ASYNC,
            GstRuntime.State.PLAYING,
            GstRuntime.State.NULL,
        ),
        (
            GstRuntime.StateChangeReturn.SUCCESS,
            GstRuntime.State.NULL,
            GstRuntime.State.VOID_PENDING,
        ),
    ]
    return pipeline


def create_runtime_with_managed_pipeline(
    event_sink: PipelineEventSink,
) -> tuple[GStreamerRuntime, str, MagicMock, MagicMock]:
    runtime = GStreamerRuntime(MagicMock())
    session_id = "pipeline-session"
    bus = MagicMock()
    pipeline = MagicMock()
    runtime._pipelines[session_id] = ManagedPipeline(
        pipeline=pipeline,
        bus=bus,
        bus_handler_id=1,
        session_id=session_id,
        event_sink=event_sink,
    )
    return runtime, session_id, bus, pipeline
