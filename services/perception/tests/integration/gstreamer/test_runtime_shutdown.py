# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from concurrent.futures import Future
from threading import Event, Thread
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, call

import gi
import pytest

gi.require_version("Gst", "1.0")
from gi.repository import Gst as GstRuntime  # noqa: E402

import perception_service.gstreamer.runtime as gstreamer_runtime  # noqa: E402
from perception_service.gstreamer.errors import (  # noqa: E402
    DispatcherUnavailableError,
    PipelineError,
    RuntimeUnavailableError,
)
from perception_service.gstreamer.glib_dispatcher import GLibTaskDispatcher  # noqa: E402
from perception_service.gstreamer.runtime import (  # noqa: E402
    GStreamerRuntime,
    ManagedPipeline,
    parse_pipeline,
)

if TYPE_CHECKING:
    from gi.repository import Gst as GstTypes

from .runtime_test_support import (  # noqa: E402
    PLAYING_PIPELINE,
    create_runtime,
    mock_pipeline_with_failed_first_stop,
)

pytestmark = pytest.mark.integration


def test_runtime_readiness_tracks_lifecycle() -> None:
    runtime = create_runtime()
    try:
        assert runtime.is_ready()
    finally:
        runtime.close()

    assert not runtime.is_ready()


def test_runtime_close_stops_pipeline_and_dispatcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dispatcher = GLibTaskDispatcher(command_queue_timeout_seconds=1)
    runtime = GStreamerRuntime(
        dispatcher,
        state_change_timeout_seconds=1,
        max_pipelines=1,
    )
    pipeline = parse_pipeline(PLAYING_PIPELINE)
    monkeypatch.setattr(gstreamer_runtime, "parse_pipeline", lambda _: pipeline)

    try:
        runtime.start_pipeline("pipeline-session", PLAYING_PIPELINE)
        runtime.close()
        _, state, _ = pipeline.get_state(0)

        with pytest.raises(DispatcherUnavailableError, match="closing or closed"):
            dispatcher.execute(
                "probe closed dispatcher",
                lambda: None,
            )
    finally:
        pipeline.set_state(GstRuntime.State.NULL)
        dispatcher.close()

    assert state == GstRuntime.State.NULL


def test_shutdown_requests_all_pipelines_before_waiting_with_shared_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = GStreamerRuntime(
        MagicMock(),
        state_change_timeout_seconds=5,
        max_pipelines=2,
    )
    operations = MagicMock()

    for session_id in ("first", "second"):
        pipeline = MagicMock()
        pipeline.set_state.return_value = GstRuntime.StateChangeReturn.SUCCESS
        pipeline.get_state.return_value = (
            GstRuntime.StateChangeReturn.SUCCESS,
            GstRuntime.State.NULL,
            GstRuntime.State.VOID_PENDING,
        )
        operations.attach_mock(pipeline, session_id)
        runtime._pipelines[session_id] = ManagedPipeline(
            pipeline=pipeline,
            bus=MagicMock(),
            bus_handler_id=1,
            session_id=session_id,
            event_sink=lambda _event: None,
        )

    shutdown_times = iter((100.0, 102.0, 104.0))
    monkeypatch.setattr(gstreamer_runtime, "monotonic", lambda: next(shutdown_times))

    runtime._stop_all_pipelines()

    assert operations.mock_calls == [
        call.first.set_state(GstRuntime.State.NULL),
        call.second.set_state(GstRuntime.State.NULL),
        call.first.get_state(3 * GstRuntime.SECOND),
        call.second.get_state(1 * GstRuntime.SECOND),
    ]
    assert not runtime._pipelines


def test_failed_close_remains_retryable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = mock_pipeline_with_failed_first_stop()
    monkeypatch.setattr(
        gstreamer_runtime,
        "parse_pipeline",
        lambda _: cast("GstTypes.Pipeline", pipeline),
    )
    runtime = create_runtime()
    pipeline_id = "pipeline-session"
    runtime.start_pipeline(pipeline_id, PLAYING_PIPELINE)

    with pytest.raises(PipelineError, match="failed to stop 1 pipeline"):
        runtime.close()

    retained_pipeline = runtime.has_pipeline(pipeline_id)
    runtime.close()

    assert retained_pipeline


def test_commands_remain_rejected_while_close_finishes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop_started = Event()
    allow_stop = Event()
    pipeline = parse_pipeline(PLAYING_PIPELINE)
    blocked_pipeline = MagicMock(wraps=pipeline)

    def set_pipeline_state(state: GstTypes.State) -> GstTypes.StateChangeReturn:
        if state == GstRuntime.State.NULL:
            stop_started.set()
            allow_stop.wait(timeout=5)
        return pipeline.set_state(state)

    blocked_pipeline.set_state.side_effect = set_pipeline_state
    monkeypatch.setattr(
        gstreamer_runtime,
        "parse_pipeline",
        lambda _: cast("GstTypes.Pipeline", blocked_pipeline),
    )
    runtime = create_runtime(
        command_queue_timeout_seconds=0.05,
        state_change_timeout_seconds=0.01,
        max_pipelines=2,
    )
    runtime.start_pipeline("pipeline-session", PLAYING_PIPELINE)
    close_completion: Future[None] = Future()

    def close_runtime() -> None:
        try:
            runtime.close()
        except Exception as error:
            close_completion.set_exception(error)
        else:
            close_completion.set_result(None)

    close_thread = Thread(target=close_runtime)
    close_thread.start()
    try:
        assert stop_started.wait(timeout=1)
        with pytest.raises(RuntimeUnavailableError, match="closing or closed"):
            runtime.start_pipeline("rejected", PLAYING_PIPELINE)
    finally:
        allow_stop.set()
        close_thread.join(timeout=1)

    close_completion.result()
    assert not close_thread.is_alive()
