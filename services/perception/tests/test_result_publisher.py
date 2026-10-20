# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

import threading

import pytest

from cairn.messaging.v1.messaging_pb2 import CairnEvent
from perception_service.opk.frame_results import FrameResultRecord
from perception_service.messaging.result_publisher import (
    EVENT_ORIGIN,
    RESULT_EVENT_TYPE,
    RedisResultPublisher,
    ResultStats,
    source_frame_gap,
)
from redis.exceptions import ConnectionError

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("previous", "current", "missing"),
    [(None, 4, 0), (4, 5, 0), (4, 8, 3), (8, 4, 0), (4, 4, 0)],
)
def test_source_frame_gap(previous: int | None, current: int, missing: int) -> None:
    assert source_frame_gap(previous, current) == missing


def result_record(frame_counter: int) -> FrameResultRecord:
    return FrameResultRecord(
        source_frame_counter=frame_counter,
        packet=frame_counter.to_bytes(),
    )


def decode_event(payload: bytes) -> CairnEvent:
    return CairnEvent.FromString(payload)


def test_bounded_queue_drops_the_oldest_result() -> None:
    published: list[int] = []
    received = threading.Event()

    def publish(_channel: str, payload: bytes) -> None:
        published.append(int.from_bytes(decode_event(payload).payload))
        if len(published) == 2:
            received.set()

    stats = ResultStats()
    publisher = RedisResultPublisher(publish, stats, max_queue_size=2)
    publisher.submit("session-123", result_record(0))
    publisher.submit("session-123", result_record(1))
    publisher.submit("session-123", result_record(2))

    with publisher:
        assert received.wait(1)

    assert published == [1, 2]
    assert stats.snapshot()["queue_drops"] == 1


def test_failed_results_are_not_retried_and_future_result_recovers() -> None:
    attempted: list[int] = []
    failed = threading.Event()
    recovered = threading.Event()

    def publish(_channel: str, payload: bytes) -> None:
        frame_counter = int.from_bytes(decode_event(payload).payload)
        attempted.append(frame_counter)
        if frame_counter < 2:
            if frame_counter == 1:
                failed.set()
            raise ConnectionError("Redis unavailable")
        recovered.set()

    stats = ResultStats()
    with RedisResultPublisher(publish, stats, max_queue_size=2) as publisher:
        publisher.submit("session-123", result_record(0))
        publisher.submit("session-123", result_record(1))
        assert failed.wait(1)
        publisher.submit("session-123", result_record(2))
        assert recovered.wait(1)

    assert attempted == [0, 1, 2]
    assert stats.snapshot()["publish_failures"] == 2
    assert stats.snapshot()["reconnects"] == 1


def test_unexpected_publish_failure_does_not_stop_the_worker() -> None:
    attempted: list[int] = []
    recovered = threading.Event()

    def publish(_channel: str, payload: bytes) -> None:
        frame_counter = int.from_bytes(decode_event(payload).payload)
        attempted.append(frame_counter)
        if frame_counter == 0:
            raise RuntimeError("unexpected failure")
        recovered.set()

    stats = ResultStats()
    with RedisResultPublisher(publish, stats) as publisher:
        publisher.submit("session-123", result_record(0))
        publisher.submit("session-123", result_record(1))
        assert recovered.wait(1)

    assert attempted == [0, 1]
    assert stats.snapshot()["publish_failures"] == 1


def test_publishes_the_canonical_cairn_event() -> None:
    published: list[tuple[str, bytes]] = []
    received = threading.Event()

    def publish(channel: str, payload: bytes) -> None:
        published.append((channel, payload))
        received.set()

    with RedisResultPublisher(publish, ResultStats()) as publisher:
        publisher.submit("session-123", result_record(7))
        assert received.wait(1)

    channel, payload = published[0]
    event = decode_event(payload)
    assert channel == "cairn.perception.sessions.session-123.results"
    assert event.origin == EVENT_ORIGIN
    assert event.event_type == RESULT_EVENT_TYPE
    assert event.topic == channel
    assert event.HasField("timestamp")
    assert event.payload == b"\x07"


def test_start_rejects_an_already_running_publisher() -> None:
    publisher = RedisResultPublisher(
        lambda _channel, _payload: None,
        ResultStats(),
    )
    with publisher:
        with pytest.raises(RuntimeError, match="already running"):
            publisher.start()


def test_stop_discards_pending_results_before_restart() -> None:
    attempted: list[int] = []
    publishing = threading.Event()
    release = threading.Event()
    restarted = threading.Event()

    def publish(_channel: str, payload: bytes) -> None:
        frame_counter = int.from_bytes(decode_event(payload).payload)
        attempted.append(frame_counter)
        if frame_counter == 0:
            publishing.set()
            release.wait(1)
        else:
            restarted.set()

    publisher = RedisResultPublisher(publish, ResultStats())
    publisher.start()
    publisher.submit("session-123", result_record(0))
    assert publishing.wait(1)
    publisher.submit("session-123", result_record(1))

    stopper = threading.Thread(target=publisher.stop)
    stopper.start()
    assert publisher._stop.wait(1)
    release.set()
    stopper.join(1)
    assert not stopper.is_alive()

    publisher.start()
    publisher.submit("session-123", result_record(2))
    assert restarted.wait(1)
    publisher.stop()

    assert attempted == [0, 2]
