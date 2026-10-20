# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import queue
import threading
from collections import Counter
from collections.abc import Callable
from enum import StrEnum
from types import TracebackType
from typing import Self

from cairn.messaging.v1.messaging_pb2 import CairnEvent
from loguru import logger
from perception_service.messaging import EVENT_ORIGIN
from perception_service.messaging.topics import session_topic
from perception_service.opk.frame_results import FrameResultRecord
from redis.exceptions import RedisError

RedisPublish = Callable[[str, bytes], object]
RESULT_EVENT_TYPE = "cairn.perception.result"


class ResultStat(StrEnum):
    QUEUE_DROPS = "queue_drops"
    SOURCE_FRAME_GAPS = "source_frame_gaps"
    PARSE_FAILURES = "parse_failures"
    PUBLISH_FAILURES = "publish_failures"
    RECONNECTS = "reconnects"


class ResultStats:
    def __init__(self) -> None:
        self._counts: Counter[ResultStat] = Counter()
        self._lock = threading.Lock()

    def increment(self, name: ResultStat, amount: int = 1) -> int:
        with self._lock:
            self._counts[name] += amount
            return self._counts[name]

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {name.value: self._counts[name] for name in ResultStat}


def source_frame_gap(previous: int | None, current: int) -> int:
    return 0 if previous is None else max(0, current - previous - 1)


def result_event(result: FrameResultRecord, topic: str) -> CairnEvent:
    event = CairnEvent(
        origin=EVENT_ORIGIN,
        event_type=RESULT_EVENT_TYPE,
        topic=topic,
        payload=result.packet,
    )
    event.timestamp.GetCurrentTime()
    return event


class _RedisPublisher:
    def __init__(
        self,
        publish: RedisPublish,
        stats: ResultStats,
        max_queue_size: int = 64,
        *,
        queue_name: str,
    ) -> None:
        if max_queue_size < 1:
            raise ValueError("max_queue_size must be positive")
        self._publish = publish
        self._stats = stats
        self._queue_name = queue_name
        self._queue: queue.Queue[CairnEvent] = queue.Queue(max_queue_size)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _submit(self, event: CairnEvent) -> None:
        while True:
            try:
                self._queue.put_nowait(event)
                return
            except queue.Full:
                try:
                    dropped = self._queue.get_nowait()
                except queue.Empty:
                    continue
                self._queue.task_done()
                total = self._stats.increment(ResultStat.QUEUE_DROPS)
                logger.warning(
                    "Redis {} queue full; dropped {} (queue_drops={})",
                    self._queue_name,
                    dropped.event_type,
                    total,
                )

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError(f"Redis {self._queue_name} publisher is already running")
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"redis-{self._queue_name}-publisher",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break
            self._queue.task_done()

    def _run(self) -> None:
        disconnected = False
        while not self._stop.is_set():
            try:
                event = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._publish(event.topic, event.SerializeToString())
            except RedisError as error:
                failures = self._stats.increment(ResultStat.PUBLISH_FAILURES)
                if not disconnected:
                    logger.warning(
                        "Redis {} publish failed (publish_failures={}): {}",
                        self._queue_name,
                        failures,
                        error,
                    )
                    disconnected = True
            except Exception:
                failures = self._stats.increment(ResultStat.PUBLISH_FAILURES)
                logger.exception(
                    "Unexpected Redis {} publish failure (publish_failures={})",
                    self._queue_name,
                    failures,
                )
            else:
                if disconnected:
                    reconnects = self._stats.increment(ResultStat.RECONNECTS)
                    logger.info(
                        "Redis {} publication recovered (reconnects={})",
                        self._queue_name,
                        reconnects,
                    )
                    disconnected = False
            finally:
                self._queue.task_done()

    def __enter__(self) -> Self:
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()


class RedisEventPublisher(_RedisPublisher):
    def submit(self, event: CairnEvent) -> None:
        self._submit(event)


class RedisResultPublisher(_RedisPublisher):
    def __init__(
        self,
        publish: RedisPublish,
        stats: ResultStats,
        max_queue_size: int = 64,
    ) -> None:
        super().__init__(
            publish,
            stats,
            max_queue_size,
            queue_name="result",
        )

    def submit(self, session_id: str, result: FrameResultRecord) -> None:
        topic = session_topic(session_id, "results")
        self._submit(result_event(result, topic))
