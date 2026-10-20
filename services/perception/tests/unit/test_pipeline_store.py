# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from dataclasses import FrozenInstanceError

import pytest

from perception_service.pipeline_store import PipelineStore
from perception_service.pipeline_types import (
    PipelineSnapshot,
    PipelineState,
    PipelineStatus,
    RuntimePipelineEvent,
    RuntimePipelineEventKind,
)

pytestmark = pytest.mark.unit


def test_store_tracks_supported_lifecycle_states() -> None:
    store = PipelineStore()
    session_id = "pipeline-1"
    store.register_pipeline(session_id)

    starting = store.get_snapshot(session_id)
    store.apply_runtime_event(
        RuntimePipelineEvent(session_id, RuntimePipelineEventKind.ATTACHED)
    )
    running = store.apply_runtime_event(
        RuntimePipelineEvent(session_id, RuntimePipelineEventKind.PLAYING)
    )
    stopping = store.mark_stopping(session_id)
    stopped = store.apply_runtime_event(
        RuntimePipelineEvent(session_id, RuntimePipelineEventKind.RELEASED)
    )

    assert starting == PipelineSnapshot(
        session_id,
        PipelineStatus(PipelineState.STARTING),
    )
    assert running is not None
    assert running.status.state == PipelineState.RUNNING
    assert stopping is not None
    assert stopping.status.state == PipelineState.STOPPING
    assert stopped is not None
    assert stopped.status.state == PipelineState.STOPPED


def test_store_returns_immutable_snapshots() -> None:
    snapshot = PipelineStore().register_pipeline("pipeline-1")

    with pytest.raises(FrozenInstanceError):
        snapshot.status = PipelineStatus(  # ty: ignore[invalid-assignment]
            PipelineState.RUNNING
        )


def test_store_ignores_delayed_events_after_release() -> None:
    store = PipelineStore()
    session_id = "pipeline-1"
    store.register_pipeline(session_id)
    released = store.apply_runtime_event(
        RuntimePipelineEvent(session_id, RuntimePipelineEventKind.RELEASED)
    )

    delayed = store.apply_runtime_event(
        RuntimePipelineEvent(
            session_id, RuntimePipelineEventKind.ERROR, "delayed failure"
        )
    )

    assert delayed is None
    assert store.get_snapshot(session_id) == released


def test_store_preserves_the_first_useful_failure_after_runtime_error() -> None:
    store = PipelineStore()
    session_id = "pipeline-1"
    store.register_pipeline(session_id)
    store.apply_runtime_event(
        RuntimePipelineEvent(session_id, RuntimePipelineEventKind.ATTACHED)
    )

    store.apply_runtime_event(
        RuntimePipelineEvent(session_id, RuntimePipelineEventKind.ERROR)
    )
    store.apply_runtime_event(
        RuntimePipelineEvent(
            session_id, RuntimePipelineEventKind.ERROR, "first useful failure"
        )
    )
    store.apply_runtime_event(
        RuntimePipelineEvent(
            session_id, RuntimePipelineEventKind.ERROR, "later failure"
        )
    )
    store.apply_runtime_event(
        RuntimePipelineEvent(session_id, RuntimePipelineEventKind.RELEASED)
    )

    snapshot = store.get_snapshot(session_id)
    assert snapshot is not None
    assert snapshot.status == PipelineStatus(
        PipelineState.FAILED,
        "first useful failure",
    )


def test_store_preserves_the_first_useful_failure_after_record_failure() -> None:
    store = PipelineStore()
    session_id = "pipeline-1"
    store.register_pipeline(session_id)
    store.apply_runtime_event(
        RuntimePipelineEvent(session_id, RuntimePipelineEventKind.ATTACHED)
    )

    store.apply_runtime_event(
        RuntimePipelineEvent(session_id, RuntimePipelineEventKind.ERROR)
    )
    store.apply_runtime_event(
        RuntimePipelineEvent(
            session_id, RuntimePipelineEventKind.ERROR, "first useful failure"
        )
    )
    store.record_failure(session_id, "later failure")
    store.apply_runtime_event(
        RuntimePipelineEvent(session_id, RuntimePipelineEventKind.RELEASED)
    )

    snapshot = store.get_snapshot(session_id)
    assert snapshot is not None
    assert snapshot.status == PipelineStatus(
        PipelineState.FAILED,
        "first useful failure",
    )


def test_store_does_not_record_failure_for_unknown_session() -> None:
    store = PipelineStore()

    assert store.record_failure("unknown", "startup failed") is None
    assert store.get_snapshot("unknown") is None


def test_store_retains_all_records_until_explicit_discard() -> None:
    store = PipelineStore()
    session_ids = [f"pipeline-{index}" for index in range(40)]
    for session_id in session_ids:
        store.register_pipeline(session_id)
        with pytest.raises(ValueError, match="already exists"):
            store.register_pipeline(session_id)

    for session_id in session_ids:
        store.apply_runtime_event(
            RuntimePipelineEvent(session_id, RuntimePipelineEventKind.RELEASED)
        )
        with pytest.raises(ValueError, match="already exists"):
            store.register_pipeline(session_id)

    assert all(store.get_snapshot(session_id) is not None for session_id in session_ids)


def test_store_discards_only_the_requested_session() -> None:
    store = PipelineStore()
    store.register_pipeline("pipeline-1")
    store.register_pipeline("pipeline-2")

    assert store.discard_pipeline("unknown") is None
    assert store.get_snapshot("pipeline-1") is not None
    assert store.discard_pipeline("pipeline-1") == PipelineSnapshot(
        "pipeline-1", PipelineStatus(PipelineState.STARTING)
    )
    assert store.get_snapshot("pipeline-1") is None
    assert store.discard_pipeline("pipeline-1") is None
    assert store.get_snapshot("pipeline-2") is not None
