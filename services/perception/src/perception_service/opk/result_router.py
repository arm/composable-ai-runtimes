# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import threading
from types import TracebackType
from typing import Any, Self

from loguru import logger

from perception_service.errors import InternalError
from perception_service.opk.frame_results import (
    FrameResultRecord,
    FrameResultsValidationError,
)
from perception_service.messaging.result_publisher import (
    RedisResultPublisher,
    ResultStat,
    ResultStats,
    source_frame_gap,
)
from perception_service.opk.endpoint_pool import OpkCommEndpointLease
from perception_service.opk.ingress import OpkIngress


class ResultRoutingError(InternalError):
    pass


class OpkResultRouter:
    def __init__(
        self,
        publisher: RedisResultPublisher,
        stats: ResultStats,
    ) -> None:
        self._publisher = publisher
        self._stats = stats
        self._lock = threading.Lock()
        self._connections: dict[str, tuple[OpkCommEndpointLease, OpkIngress]] = {}
        self._last_frame_counters: dict[str, int] = {}

    def start(self, session_id: str, lease: OpkCommEndpointLease) -> None:
        endpoint = lease.endpoint
        ingress = OpkIngress(
            lambda record: self._accept_record(session_id, record),
            host=endpoint.host,
            port=endpoint.port,
            on_drop=lambda: self._record_parse_failure(session_id),
        )
        with self._lock:
            if session_id in self._connections:
                raise ResultRoutingError(
                    f"result routing already exists for {session_id!r}"
                )
            self._connections[session_id] = (lease, ingress)
            try:
                ingress.start()
            except Exception as error:
                self._connections.pop(session_id)
                raise ResultRoutingError(
                    f"failed to start result routing for {session_id!r}"
                ) from error

    def stop(self, session_id: str) -> None:
        with self._lock:
            connection = self._connections.pop(session_id, None)
            self._last_frame_counters.pop(session_id, None)
            if connection is None:
                return
            lease, ingress = connection
        try:
            ingress.stop()
        except Exception as error:
            raise ResultRoutingError(
                f"failed to stop result routing for {session_id!r}"
            ) from error
        finally:
            lease.release()

    def _accept_record(self, session_id: str, record: dict[str, Any]) -> None:
        try:
            result = FrameResultRecord.from_opk_record(record)
        except FrameResultsValidationError as error:
            self._record_parse_failure(session_id)
            logger.warning("Dropping invalid OPK result for {}: {}", session_id, error)
            return

        with self._lock:
            if session_id not in self._connections:
                return
            previous = self._last_frame_counters.get(session_id)
            if previous is None or result.source_frame_counter > previous:
                self._last_frame_counters[session_id] = result.source_frame_counter

        missing = source_frame_gap(previous, result.source_frame_counter)
        if missing:
            total = self._stats.increment(ResultStat.SOURCE_FRAME_GAPS, missing)
            logger.warning(
                "OPK source-frame gap for {}: {} frames before {} "
                "(source_frame_gaps={})",
                session_id,
                missing,
                result.source_frame_counter,
                total,
            )

        self._publisher.submit(session_id, result)

    def _record_parse_failure(self, session_id: str) -> None:
        with self._lock:
            if session_id not in self._connections:
                return
        self._stats.increment(ResultStat.PARSE_FAILURES)

    def close(self) -> None:
        with self._lock:
            session_ids = tuple(self._connections)
        errors: list[Exception] = []
        for session_id in session_ids:
            try:
                self.stop(session_id)
            except Exception as error:
                errors.append(error)
        if errors:
            raise ResultRoutingError(
                f"failed to close result routing for {len(errors)} session(s)"
            ) from ExceptionGroup("result router cleanup failures", errors)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
