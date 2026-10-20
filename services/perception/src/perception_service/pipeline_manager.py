# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from threading import Lock
from typing import TYPE_CHECKING

from loguru import logger

from perception_service.pipeline_store import PipelineStore
from perception_service.pipeline_types import (
    PipelineSnapshot,
    RuntimePipelineEvent,
    RuntimePipelineEventKind,
)

if TYPE_CHECKING:
    from perception_service.gstreamer.runtime import GStreamerRuntime


@dataclass(frozen=True)
class PipelineEvent:
    kind: RuntimePipelineEventKind
    snapshot: PipelineSnapshot
    source_name: str | None = None
    from_runtime: bool = False


type PipelineEventSubscriber = Callable[[PipelineEvent], None]


class PipelineEventPublisher:
    """Best-effort synchronous notifications after authoritative state updates.

    Callbacks can run on the GLib thread and must not block or call back into the
    manager. External publishers should enqueue work before returning.
    """

    def __init__(
        self,
        subscribers: Iterable[PipelineEventSubscriber] = (),
    ) -> None:
        self._subscribers = list(subscribers)
        self._lock = Lock()

    def subscribe(self, subscriber: PipelineEventSubscriber) -> None:
        with self._lock:
            self._subscribers.append(subscriber)

    def publish(self, event: PipelineEvent) -> None:
        with self._lock:
            subscribers = tuple(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber(event)
            except Exception:
                logger.exception(
                    "Pipeline event subscriber {!r} failed for session {} ({})",
                    subscriber,
                    event.snapshot.session_id,
                    event.kind,
                )


class PipelineManager:
    def __init__(
        self,
        backend: GStreamerRuntime,
        store: PipelineStore,
    ) -> None:
        self._backend = backend
        self._store = store
        self._publisher = PipelineEventPublisher()
        self._event_lock = Lock()

    def subscribe(self, subscriber: PipelineEventSubscriber) -> None:
        self._publisher.subscribe(subscriber)

    def start_pipeline(
        self,
        session_id: str,
        description: str,
    ) -> None:
        with self._event_lock:
            self._store.register_pipeline(session_id)

        try:
            self._backend.start_pipeline(
                session_id, description, self._handle_runtime_event
            )
        except Exception as error:
            self._record_failure_and_publish(session_id, str(error))
            try:
                self._backend.stop_pipeline(session_id)
            except Exception:
                logger.exception(
                    "Pipeline {} cleanup after startup failure failed",
                    session_id,
                )
            raise

    def get_pipeline(self, session_id: str) -> PipelineSnapshot | None:
        with self._event_lock:
            return self._store.get_snapshot(session_id)

    def discard_pipeline(self, session_id: str) -> PipelineSnapshot | None:
        with self._event_lock:
            return self._store.discard_pipeline(session_id)

    def stop_pipeline(self, session_id: str) -> None:
        with self._event_lock:
            self._store.mark_stopping(session_id)

        try:
            self._backend.stop_pipeline(session_id)
        except Exception as error:
            self._record_failure_and_publish(session_id, str(error))
            raise

    def is_ready(self) -> bool:
        return self._backend.is_ready()

    def set_inference_stage_active(
        self,
        session_id: str,
        stage_id: str,
        active: bool,
    ) -> bool:
        return self._backend.set_inference_stage_active(session_id, stage_id, active)

    def _record_failure_and_publish(self, session_id: str, message: str) -> None:
        with self._event_lock:
            before = self._store.get_snapshot(session_id)
            snapshot = self._store.record_failure(session_id, message)
            if snapshot is not None and snapshot != before:
                self._publisher.publish(
                    PipelineEvent(RuntimePipelineEventKind.ERROR, snapshot)
                )

    def _handle_runtime_event(self, event: RuntimePipelineEvent) -> None:
        with self._event_lock:
            snapshot = self._store.apply_runtime_event(event)
            if snapshot is None:
                return

            self._publisher.publish(
                PipelineEvent(
                    event.kind, snapshot, event.source_name, from_runtime=True
                )
            )
