# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, call

import gi
import pytest

gi.require_version("Gst", "1.0")
from gi.repository import GLib as GLibRuntime  # noqa: E402
from gi.repository import Gst as GstRuntime  # noqa: E402

import perception_service.gstreamer.runtime as gstreamer_runtime  # noqa: E402
from perception_service.errors import ResourceExhaustedError  # noqa: E402
from perception_service.gstreamer.errors import PipelineError  # noqa: E402

if TYPE_CHECKING:
    from gi.repository import Gst as GstTypes

from .runtime_test_support import (  # noqa: E402
    PLAYING_PIPELINE,
    create_runtime,
    mock_pipeline_with_failed_first_stop,
)

pytestmark = pytest.mark.integration


def test_runtime_starts_and_stops_pipeline() -> None:
    with create_runtime() as runtime:
        first_pipeline_id = "first"
        second_pipeline_id = "second"
        runtime.start_pipeline(first_pipeline_id, PLAYING_PIPELINE)
        runtime.start_pipeline(second_pipeline_id, PLAYING_PIPELINE)

        first_pipeline_is_running = runtime.has_pipeline(first_pipeline_id)
        second_pipeline_is_running = runtime.has_pipeline(second_pipeline_id)
        runtime.stop_pipeline(first_pipeline_id)
        first_pipeline_is_stopped = not runtime.has_pipeline(first_pipeline_id)
        runtime.stop_pipeline(second_pipeline_id)

    assert first_pipeline_is_running
    assert second_pipeline_is_running
    assert first_pipeline_is_stopped


def test_runtime_stop_pipeline_is_idempotent() -> None:
    with create_runtime() as runtime:
        runtime.stop_pipeline("missing-session")
        pipeline_is_absent = not runtime.has_pipeline("missing-session")

    assert pipeline_is_absent


def test_runtime_accepts_a_pipeline_after_an_invalid_description() -> None:
    with create_runtime() as runtime:
        with pytest.raises(GLibRuntime.Error):
            runtime.start_pipeline("invalid", "this-element-does-not-exist ! fakesink")

        pipeline_id = "pipeline-session"
        runtime.start_pipeline(pipeline_id, PLAYING_PIPELINE)
        pipeline_is_running = runtime.has_pipeline(pipeline_id)

    assert pipeline_is_running


def test_failed_startup_cleanup_is_retried_during_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bus = MagicMock()
    bus.connect.return_value = 1
    failed_pipeline = MagicMock()
    failed_pipeline.get_bus.return_value = bus
    failed_pipeline.set_state.side_effect = [
        GstRuntime.StateChangeReturn.SUCCESS,
        GstRuntime.StateChangeReturn.ASYNC,
        GstRuntime.StateChangeReturn.SUCCESS,
    ]
    failed_pipeline.get_state.side_effect = [
        (
            GstRuntime.StateChangeReturn.ASYNC,
            GstRuntime.State.PAUSED,
            GstRuntime.State.PLAYING,
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
    monkeypatch.setattr(
        gstreamer_runtime,
        "parse_pipeline",
        lambda _: cast("GstTypes.Pipeline", failed_pipeline),
    )
    runtime = create_runtime(max_pipelines=1)

    try:
        with pytest.raises(PipelineError, match="did not reach PLAYING"):
            runtime.start_pipeline("failed-start", PLAYING_PIPELINE)

        with pytest.raises(ResourceExhaustedError, match="pipeline limit"):
            runtime.start_pipeline("another-pipeline", PLAYING_PIPELINE)

        disconnects_after_startup = bus.disconnect.call_count
        watch_removals_after_startup = bus.remove_signal_watch.call_count
        runtime.close()
    finally:
        runtime.close()

    assert disconnects_after_startup == 0
    assert watch_removals_after_startup == 0
    assert failed_pipeline.set_state.call_args_list == [
        call(GstRuntime.State.PLAYING),
        call(GstRuntime.State.NULL),
        call(GstRuntime.State.NULL),
    ]
    bus.disconnect.assert_called_once_with(1)
    bus.remove_signal_watch.assert_called_once_with()


def test_failed_stop_retains_pipeline_for_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pipeline = mock_pipeline_with_failed_first_stop()
    monkeypatch.setattr(
        gstreamer_runtime,
        "parse_pipeline",
        lambda _: cast("GstTypes.Pipeline", pipeline),
    )
    runtime = create_runtime()
    try:
        pipeline_id = "pipeline-session"
        runtime.start_pipeline(pipeline_id, PLAYING_PIPELINE)

        with pytest.raises(PipelineError, match="did not reach NULL"):
            runtime.stop_pipeline(pipeline_id)

        retained_pipeline = runtime.has_pipeline(pipeline_id)
        runtime.stop_pipeline(pipeline_id)
        stopped_after_retry = not runtime.has_pipeline(pipeline_id)
    finally:
        runtime.close()

    assert retained_pipeline
    assert stopped_after_retry
