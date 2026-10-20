# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
from threading import Lock

from perception_service.pipeline_types import (
    PipelineSnapshot,
    PipelineState,
    PipelineStatus,
    RuntimePipelineEvent,
    RuntimePipelineEventKind,
)


@dataclass
class _PipelineRecord:
    session_id: str
    status: PipelineStatus
    released: bool = False


def _first_useful_failure_message(
    current_status: PipelineStatus,
    event_message: str | None,
) -> str | None:
    if current_status.state == PipelineState.FAILED and current_status.message:
        return current_status.message
    return event_message or current_status.message


class PipelineStore:
    def __init__(self) -> None:
        self._records: dict[str, _PipelineRecord] = {}
        self._lock = Lock()

    def register_pipeline(self, session_id: str) -> PipelineSnapshot:
        with self._lock:
            if session_id in self._records:
                raise ValueError(f"pipeline already exists with ID {session_id!r}")

            record = _PipelineRecord(
                session_id=session_id,
                status=PipelineStatus(PipelineState.STARTING),
            )
            self._records[session_id] = record
            return self._snapshot(record)

    def get_snapshot(self, session_id: str) -> PipelineSnapshot | None:
        with self._lock:
            record = self._records.get(session_id)
            return self._snapshot(record) if record else None

    def discard_pipeline(self, session_id: str) -> PipelineSnapshot | None:
        with self._lock:
            record = self._records.pop(session_id, None)
            return self._snapshot(record) if record is not None else None

    def mark_stopping(self, session_id: str) -> PipelineSnapshot | None:
        with self._lock:
            record = self._records.get(session_id)
            if record is None:
                return None
            if not record.released and record.status.state != PipelineState.FAILED:
                record.status = PipelineStatus(PipelineState.STOPPING)
            return self._snapshot(record)

    def apply_runtime_event(
        self,
        event: RuntimePipelineEvent,
    ) -> PipelineSnapshot | None:
        with self._lock:
            record = self._records.get(event.session_id)
            if record is None or record.released:
                return None

            match event.kind:
                case RuntimePipelineEventKind.PLAYING:
                    if record.status.state == PipelineState.STARTING:
                        record.status = PipelineStatus(PipelineState.RUNNING)
                case RuntimePipelineEventKind.ERROR:
                    record.status = PipelineStatus(
                        PipelineState.FAILED,
                        _first_useful_failure_message(record.status, event.message),
                    )
                case RuntimePipelineEventKind.END_OF_STREAM:
                    if record.status.state != PipelineState.FAILED:
                        record.status = PipelineStatus(PipelineState.STOPPED)
                case RuntimePipelineEventKind.RELEASED:
                    record.released = True
                    if record.status.state != PipelineState.FAILED:
                        record.status = PipelineStatus(PipelineState.STOPPED)

            return self._snapshot(record)

    def record_failure(
        self,
        session_id: str,
        message: str | None,
    ) -> PipelineSnapshot | None:
        with self._lock:
            record = self._records.get(session_id)
            if record is None:
                return None

            record.status = PipelineStatus(
                PipelineState.FAILED,
                _first_useful_failure_message(record.status, message),
            )
            return self._snapshot(record)

    @staticmethod
    def _snapshot(record: _PipelineRecord) -> PipelineSnapshot:
        return PipelineSnapshot(record.session_id, record.status)
