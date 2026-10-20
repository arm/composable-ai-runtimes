# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import json
import threading
from collections.abc import Iterable
from enum import StrEnum

from cairn.messaging.v1.messaging_pb2 import CairnEvent
from perception_service.messaging import EVENT_ORIGIN
from perception_service.messaging.result_publisher import RedisEventPublisher
from perception_service.messaging.topics import session_topic


class SessionState(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class StageState(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"


class LifecyclePublisher:
    def __init__(self, publisher: RedisEventPublisher) -> None:
        self._publisher = publisher
        self._session_stage_ids: dict[str, frozenset[str]] = {}
        self._lock = threading.Lock()

    def start_session(
        self,
        session_id: str,
        stage_ids: Iterable[str],
        *,
        enabled: bool,
    ) -> str:
        if not enabled:
            return ""

        with self._lock:
            if session_id in self._session_stage_ids:
                raise ValueError(f"lifecycle already exists for {session_id!r}")
            self._session_stage_ids[session_id] = frozenset(stage_ids)
            state = SessionState.STARTING
            self._publish(
                session_id=session_id,
                event_type=f"cairn.perception.session.{state.value}",
                payload={"session_id": session_id, "state": state.value},
            )
        return session_topic(session_id, "events")

    def publish_session(
        self,
        session_id: str,
        state: SessionState,
        stage_id: str | None = None,
    ) -> None:
        with self._lock:
            if state in (SessionState.STOPPED, SessionState.FAILED):
                stage_ids = self._session_stage_ids.pop(session_id, None)
            else:
                stage_ids = self._session_stage_ids.get(session_id)
            if stage_ids is None:
                return
            payload = {"session_id": session_id, "state": state.value}
            if stage_id is not None and stage_id in stage_ids:
                payload["stage_id"] = stage_id
            self._publish(
                session_id=session_id,
                event_type=f"cairn.perception.session.{state.value}",
                payload=payload,
            )

    def publish_stage(
        self,
        session_id: str,
        stage_id: str,
        state: StageState,
    ) -> None:
        with self._lock:
            stage_ids = self._session_stage_ids.get(session_id)
            if stage_ids is None or stage_id not in stage_ids:
                return
            self._publish(
                session_id=session_id,
                event_type=f"cairn.perception.stage.{state.value}",
                payload={
                    "session_id": session_id,
                    "stage_id": stage_id,
                    "state": state.value,
                },
            )

    def _publish(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, str],
    ) -> None:
        topic = session_topic(session_id, "events")
        event = CairnEvent(
            origin=EVENT_ORIGIN,
            event_type=event_type,
            topic=topic,
            payload=json.dumps(
                payload,
                separators=(",", ":"),
                sort_keys=True,
            ).encode(),
        )
        event.timestamp.GetCurrentTime()
        self._publisher.submit(event)
