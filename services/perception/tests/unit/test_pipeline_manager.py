# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

import pytest
from loguru import logger

from perception_service.pipeline_manager import (
    PipelineEvent,
    PipelineEventPublisher,
    PipelineManager,
)
from perception_service.pipeline_store import PipelineStore
from perception_service.pipeline_types import (
    PipelineEventSink,
    PipelineSnapshot,
    PipelineState,
    PipelineStatus,
    RuntimePipelineEvent,
    RuntimePipelineEventKind,
)

if TYPE_CHECKING:
    from perception_service.gstreamer.runtime import GStreamerRuntime

pytestmark = pytest.mark.unit


def runtime_event(
    session_id: str,
    kind: RuntimePipelineEventKind,
    message: str | None = None,
) -> RuntimePipelineEvent:
    return RuntimePipelineEvent(session_id, kind, message)


class PipelineBackendStub:
    def __init__(self) -> None:
        self.start_requests: list[tuple[str, str]] = []
        self.stop_requests: list[str] = []
        self.event_sinks: dict[str, PipelineEventSink] = {}
        self.stage_requests: list[tuple[str, str, bool]] = []
        self.ready = True
        self.start_action: Callable[[str, PipelineEventSink], None] | None = None
        self.stop_action: Callable[[str, PipelineEventSink | None], None] | None = None

    def start_pipeline(
        self,
        session_id: str,
        description: str,
        event_sink: PipelineEventSink,
    ) -> None:
        self.start_requests.append((session_id, description))
        self.event_sinks[session_id] = event_sink
        if self.start_action is not None:
            self.start_action(session_id, event_sink)

    def stop_pipeline(self, session_id: str) -> None:
        self.stop_requests.append(session_id)
        if self.stop_action is not None:
            self.stop_action(session_id, self.event_sinks.get(session_id))

    def is_ready(self) -> bool:
        return self.ready

    def set_inference_stage_active(
        self,
        session_id: str,
        stage_id: str,
        active: bool,
    ) -> bool:
        self.stage_requests.append((session_id, stage_id, active))
        return active


def test_manager_coordinates_runtime_events_and_authoritative_state() -> None:
    backend = PipelineBackendStub()
    published: list[PipelineEvent] = []
    manager = PipelineManager(cast("GStreamerRuntime", backend), PipelineStore())
    manager.subscribe(published.append)

    def start_action(session_id: str, sink: PipelineEventSink) -> None:
        assert manager.get_pipeline(session_id) == PipelineSnapshot(
            session_id, PipelineStatus(PipelineState.STARTING)
        )
        sink(runtime_event(session_id, RuntimePipelineEventKind.ATTACHED))
        sink(runtime_event(session_id, RuntimePipelineEventKind.PLAYING))

    backend.start_action = start_action
    description = "videotestsrc ! fakesink"

    session_id = "pipeline-1"
    assert manager.start_pipeline(session_id, description) is None

    assert backend.start_requests == [(session_id, description)]
    assert manager.get_pipeline(session_id) == PipelineSnapshot(
        session_id,
        PipelineStatus(PipelineState.RUNNING),
    )
    assert [(event.kind, event.snapshot.status.state) for event in published] == [
        (RuntimePipelineEventKind.ATTACHED, PipelineState.STARTING),
        (RuntimePipelineEventKind.PLAYING, PipelineState.RUNNING),
    ]


def test_manager_records_stopping_before_runtime_release() -> None:
    backend = PipelineBackendStub()
    published: list[PipelineEvent] = []
    manager = PipelineManager(cast("GStreamerRuntime", backend), PipelineStore())
    manager.subscribe(published.append)

    def start_action(session_id: str, sink: PipelineEventSink) -> None:
        sink(runtime_event(session_id, RuntimePipelineEventKind.PLAYING))

    def stop_action(
        session_id: str,
        sink: PipelineEventSink | None,
    ) -> None:
        assert manager.get_pipeline(session_id) == PipelineSnapshot(
            session_id, PipelineStatus(PipelineState.STOPPING)
        )
        assert sink is not None
        sink(runtime_event(session_id, RuntimePipelineEventKind.RELEASED))

    backend.start_action = start_action
    backend.stop_action = stop_action
    session_id = "pipeline-1"
    manager.start_pipeline(session_id, "videotestsrc ! fakesink")

    manager.stop_pipeline(session_id)

    assert backend.stop_requests == [session_id]
    assert [(event.kind, event.snapshot.status.state) for event in published] == [
        (RuntimePipelineEventKind.PLAYING, PipelineState.RUNNING),
        (RuntimePipelineEventKind.RELEASED, PipelineState.STOPPED),
    ]


def test_manager_records_stop_failure_without_losing_retryable_session() -> None:
    backend = PipelineBackendStub()
    manager = PipelineManager(cast("GStreamerRuntime", backend), PipelineStore())
    session_id = "pipeline-1"
    manager.start_pipeline(session_id, "videotestsrc ! fakesink")

    def fail_stop(
        _session_id: str,
        _sink: PipelineEventSink | None,
    ) -> None:
        raise TimeoutError("native stop timed out")

    backend.stop_action = fail_stop

    with pytest.raises(TimeoutError, match="native stop timed out"):
        manager.stop_pipeline(session_id)

    assert manager.get_pipeline(session_id) == PipelineSnapshot(
        session_id,
        PipelineStatus(PipelineState.FAILED, "native stop timed out"),
    )


def test_manager_retries_cleanup_after_start_failure_without_masking_it() -> None:
    backend = PipelineBackendStub()
    manager = PipelineManager(cast("GStreamerRuntime", backend), PipelineStore())

    def fail_start(session_id: str, sink: PipelineEventSink) -> None:
        sink(runtime_event(session_id, RuntimePipelineEventKind.ATTACHED))
        sink(
            runtime_event(
                session_id,
                RuntimePipelineEventKind.ERROR,
                "pipeline rejected PLAYING",
            )
        )
        raise RuntimeError("backend start failed")

    backend.start_action = fail_start

    session_id = "pipeline-1"
    with pytest.raises(RuntimeError, match="backend start failed"):
        manager.start_pipeline(session_id, "videotestsrc ! fakesink")

    snapshot = manager.get_pipeline("pipeline-1")
    assert snapshot is not None
    assert snapshot.status == PipelineStatus(
        PipelineState.FAILED,
        "pipeline rejected PLAYING",
    )
    assert backend.stop_requests == [snapshot.session_id]


def test_manager_preserves_start_failure_without_a_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = PipelineBackendStub()
    store = PipelineStore()
    manager = PipelineManager(cast("GStreamerRuntime", backend), store)
    published: list[PipelineEvent] = []
    manager.subscribe(published.append)
    session_id = "pipeline-1"
    error = RuntimeError("backend failed")

    def no_snapshot(_session_id: str, _message: str | None) -> None:
        return None

    def fail_start(_session_id: str, _sink: PipelineEventSink) -> None:
        raise error

    monkeypatch.setattr(store, "record_failure", no_snapshot)
    backend.start_action = fail_start

    with pytest.raises(RuntimeError) as raised:
        manager.start_pipeline(session_id, "videotestsrc ! fakesink")

    assert raised.value is error
    assert backend.stop_requests == [session_id]
    assert all(event.kind != RuntimePipelineEventKind.ERROR for event in published)


def test_manager_preserves_stop_failure_without_a_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = PipelineBackendStub()
    store = PipelineStore()
    manager = PipelineManager(cast("GStreamerRuntime", backend), store)
    published: list[PipelineEvent] = []
    manager.subscribe(published.append)
    session_id = "pipeline-1"
    error = RuntimeError("backend failed")

    def no_snapshot(_session_id: str, _message: str | None) -> None:
        return None

    def fail_stop(_session_id: str, _sink: PipelineEventSink | None) -> None:
        raise error

    monkeypatch.setattr(store, "record_failure", no_snapshot)
    manager.start_pipeline(session_id, "videotestsrc ! fakesink")
    backend.stop_action = fail_stop

    with pytest.raises(RuntimeError) as raised:
        manager.stop_pipeline(session_id)

    assert raised.value is error
    assert backend.stop_requests == [session_id]
    assert all(event.kind != RuntimePipelineEventKind.ERROR for event in published)


def test_failed_start_preserves_failure_and_forwards_events_until_release() -> None:
    backend = PipelineBackendStub()
    published: list[PipelineEvent] = []
    manager = PipelineManager(cast("GStreamerRuntime", backend), PipelineStore())
    manager.subscribe(published.append)

    def fail_start(session_id: str, sink: PipelineEventSink) -> None:
        sink(runtime_event(session_id, RuntimePipelineEventKind.ERROR))
        raise RuntimeError("backend start failed")

    def fail_cleanup(
        _session_id: str,
        _sink: PipelineEventSink | None,
    ) -> None:
        raise TimeoutError("cleanup incomplete")

    backend.start_action = fail_start
    backend.stop_action = fail_cleanup
    session_id = "pipeline-1"

    with pytest.raises(RuntimeError, match="backend start failed"):
        manager.start_pipeline(session_id, "videotestsrc ! fakesink")

    sink = backend.event_sinks[session_id]
    sink(runtime_event(session_id, RuntimePipelineEventKind.ERROR, "late failure"))
    sink(runtime_event(session_id, RuntimePipelineEventKind.RELEASED))
    sink(runtime_event(session_id, RuntimePipelineEventKind.ERROR, "after release"))

    assert backend.stop_requests == [session_id]
    assert [event.kind for event in published] == [
        RuntimePipelineEventKind.ERROR,
        RuntimePipelineEventKind.ERROR,
        RuntimePipelineEventKind.ERROR,
        RuntimePipelineEventKind.RELEASED,
    ]
    snapshot = manager.get_pipeline(session_id)
    assert snapshot is not None
    assert snapshot.status == PipelineStatus(
        PipelineState.FAILED,
        "backend start failed",
    )
    error_messages = [
        event.snapshot.status.message
        for event in published
        if event.kind == RuntimePipelineEventKind.ERROR
    ]
    assert error_messages == [None, "backend start failed", "backend start failed"]


def test_released_session_callbacks_and_stop_do_not_change_another_session() -> None:
    backend = PipelineBackendStub()
    published: list[PipelineEvent] = []
    manager = PipelineManager(cast("GStreamerRuntime", backend), PipelineStore())
    manager.subscribe(published.append)
    first, second = "pipeline-1", "pipeline-2"
    manager.start_pipeline(first, "videotestsrc ! fakesink")
    first_sink = backend.event_sinks[first]
    first_sink(runtime_event(first, RuntimePipelineEventKind.RELEASED))
    assert manager.discard_pipeline(first) == PipelineSnapshot(
        first, PipelineStatus(PipelineState.STOPPED)
    )
    assert manager.discard_pipeline(first) is None
    manager.start_pipeline(second, "videotestsrc ! fakesink")
    before = tuple(published)

    first_sink(runtime_event(first, RuntimePipelineEventKind.ERROR, "delayed"))
    manager.stop_pipeline(first)

    assert tuple(published) == before
    assert manager.get_pipeline(first) is None
    assert manager.get_pipeline(second) == PipelineSnapshot(
        second, PipelineStatus(PipelineState.STARTING)
    )
    assert backend.stop_requests == [first]
    backend.event_sinks[second](
        runtime_event(second.encode().decode(), RuntimePipelineEventKind.PLAYING)
    )
    assert manager.get_pipeline(second) == PipelineSnapshot(
        second, PipelineStatus(PipelineState.RUNNING)
    )
    manager.stop_pipeline(second.encode().decode())
    assert manager.get_pipeline(second) == PipelineSnapshot(
        second, PipelineStatus(PipelineState.STOPPING)
    )
    assert backend.stop_requests == [first, second]


def test_manager_delegates_readiness_and_stage_control() -> None:
    backend = PipelineBackendStub()
    manager = PipelineManager(cast("GStreamerRuntime", backend), PipelineStore())

    backend.ready = False
    active = manager.set_inference_stage_active("pipeline-1", "objects", True)

    assert not manager.is_ready()
    assert active
    assert backend.stage_requests == [("pipeline-1", "objects", True)]


def test_publisher_isolates_subscriber_failures() -> None:
    received: list[PipelineEvent] = []
    log_messages: list[str] = []

    def failing_subscriber(_event: PipelineEvent) -> None:
        raise RuntimeError("subscriber unavailable")

    publisher = PipelineEventPublisher([failing_subscriber, received.append])
    event = PipelineEvent(
        RuntimePipelineEventKind.PLAYING,
        PipelineSnapshot(
            "pipeline-1",
            PipelineStatus(PipelineState.RUNNING),
        ),
    )
    sink_id = logger.add(lambda message: log_messages.append(message.record["message"]))
    try:
        publisher.publish(event)
    finally:
        logger.remove(sink_id)

    assert received == [event]
    assert any(
        "failing_subscriber" in message and "pipeline-1" in message
        for message in log_messages
    )
