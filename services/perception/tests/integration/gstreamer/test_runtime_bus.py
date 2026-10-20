# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from unittest.mock import MagicMock

import gi
import pytest

gi.require_version("Gst", "1.0")
from gi.repository import Gst as GstRuntime  # noqa: E402

from perception_service.gstreamer.runtime import (  # noqa: E402
    GStreamerRuntime,
    _log_bus_message,
)
from perception_service.pipeline_manager import PipelineManager  # noqa: E402
from perception_service.pipeline_store import PipelineStore  # noqa: E402
from perception_service.pipeline_types import (  # noqa: E402
    PipelineEventSink,
    RuntimePipelineEvent,
    RuntimePipelineEventKind,
)
from perception_service.service import PerceptionService  # noqa: E402
from perception_service.messaging.lifecycle import (  # noqa: E402
    LifecyclePublisher,
    SessionState,
)

from .runtime_test_support import (  # noqa: E402
    create_runtime_with_managed_pipeline,
)

pytestmark = pytest.mark.integration


def test_runtime_dispatches_error_bus_message() -> None:
    handler = MagicMock()
    runtime, session_id, bus, _ = create_runtime_with_managed_pipeline(handler)
    message = MagicMock()
    message.type = GstRuntime.MessageType.ERROR
    message.parse_error.return_value = (MagicMock(message="source failed"), None)
    message.src.get_name.return_value = "camera-source"

    runtime._on_bus_message(bus, message, session_id)

    handler.assert_called_once_with(
        RuntimePipelineEvent(
            session_id, RuntimePipelineEventKind.ERROR, "source failed", "camera-source"
        )
    )


def test_runtime_dispatches_eos_bus_message() -> None:
    handler = MagicMock()
    runtime, session_id, bus, _ = create_runtime_with_managed_pipeline(handler)
    message = MagicMock()
    message.type = GstRuntime.MessageType.EOS

    runtime._on_bus_message(bus, message, session_id)

    handler.assert_called_once_with(
        RuntimePipelineEvent(session_id, RuntimePipelineEventKind.END_OF_STREAM)
    )


def test_runtime_logs_pipeline_state_changes(log_messages: list[str]) -> None:
    handler = MagicMock()
    runtime, session_id, bus, pipeline = create_runtime_with_managed_pipeline(handler)
    message = MagicMock()
    message.type = GstRuntime.MessageType.STATE_CHANGED
    message.src = pipeline
    message.parse_state_changed.return_value = (
        GstRuntime.State.PAUSED, GstRuntime.State.PLAYING, GstRuntime.State.VOID_PENDING
    )

    runtime._on_bus_message(bus, message, session_id)

    assert log_messages == [
        "Pipeline pipeline-session changed state from paused to playing"
    ]


def test_runtime_ignores_messages_from_an_unknown_session() -> None:
    handler = MagicMock()
    runtime, _, bus, _ = create_runtime_with_managed_pipeline(handler)
    message = MagicMock()
    message.type = GstRuntime.MessageType.ERROR

    runtime._on_bus_message(bus, message, "unknown-session")

    handler.assert_not_called()


def test_runtime_ignores_messages_from_a_stale_bus() -> None:
    handler = MagicMock()
    runtime, session_id, _, _ = create_runtime_with_managed_pipeline(handler)
    message = MagicMock()
    message.type = GstRuntime.MessageType.ERROR

    runtime._on_bus_message(MagicMock(), message, session_id)

    handler.assert_not_called()


def test_runtime_ignores_child_element_state_changes(log_messages: list[str]) -> None:
    handler = MagicMock()
    runtime, session_id, bus, _ = create_runtime_with_managed_pipeline(handler)
    message = MagicMock()
    message.type = GstRuntime.MessageType.STATE_CHANGED
    message.src = MagicMock()

    runtime._on_bus_message(bus, message, session_id)

    handler.assert_not_called()
    assert log_messages == []


def test_runtime_ignores_unhandled_bus_messages() -> None:
    handler = MagicMock()
    runtime, session_id, bus, _ = create_runtime_with_managed_pipeline(handler)
    message = MagicMock()
    message.type = GstRuntime.MessageType.WARNING

    runtime._on_bus_message(bus, message, session_id)

    handler.assert_not_called()


def test_runtime_bus_message_reports_pipeline_errors(
    log_messages: list[str],
) -> None:
    lifecycle = MagicMock(spec=LifecyclePublisher)
    error = MagicMock()
    error.message = "source failed"
    message = MagicMock()
    message.type = GstRuntime.MessageType.ERROR
    message.src.get_name.return_value = "camera-source"
    message.parse_error.return_value = (error, None)

    backend = MagicMock(spec=GStreamerRuntime)
    manager = PipelineManager(backend, PipelineStore())
    PerceptionService(manager, MagicMock(), MagicMock(), MagicMock(), lifecycle)
    manager.start_pipeline("pipeline-session", "test-pipeline")
    event_sink: PipelineEventSink = backend.start_pipeline.call_args.args[2]
    runtime, session_id, bus, _ = create_runtime_with_managed_pipeline(event_sink)
    runtime._on_bus_message(bus, message, session_id)

    assert log_messages == [
        "Pipeline pipeline-session failed in camera-source: "
        "source failed; no debug details"
    ]
    lifecycle.publish_session.assert_called_once_with(
        "pipeline-session",
        SessionState.FAILED,
        "camera-source",
    )


def test_log_bus_message_logs_end_of_stream(
    log_messages: list[str],
) -> None:
    message = MagicMock()
    message.type = GstRuntime.MessageType.EOS

    _log_bus_message("pipeline-session", message)

    assert log_messages == ["Pipeline pipeline-session reached end of stream"]


def test_log_bus_message_logs_pipeline_state_changes(
    log_messages: list[str],
) -> None:
    old_state = MagicMock()
    old_state.value_nick = "paused"
    new_state = MagicMock()
    new_state.value_nick = "playing"
    message = MagicMock()
    message.type = GstRuntime.MessageType.STATE_CHANGED
    message.parse_state_changed.return_value = (old_state, new_state, None)

    _log_bus_message("pipeline-session", message)

    assert log_messages == [
        "Pipeline pipeline-session changed state from paused to playing"
    ]
