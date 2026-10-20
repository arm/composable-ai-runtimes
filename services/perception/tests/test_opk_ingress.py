# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import threading
from typing import Any

import pytest

import perception_service.opk.ingress as opk_ingress_module
from perception_service.opk.ingress import OpkIngress, consume_messages
from websockets.sync.server import ServerConnection, serve

pytestmark = pytest.mark.unit


def encode(record: object) -> str:
    return json.dumps(record)


@pytest.mark.parametrize(
    "invalid_record",
    [b"not-json", '{"value":' + "9" * 5000 + "}", "[" * 100_000 + "0" + "]" * 100_000],
    ids=["invalid-json", "integer-limit", "nesting-limit"],
)
def test_ingress_accepts_text_and_binary_and_skips_invalid_records(
    invalid_record: str | bytes,
) -> None:
    received: list[dict[str, Any]] = []
    drops: list[None] = []

    consume_messages(
        [encode({"frame_counter": 1}), invalid_record, encode({"frame_counter": 2}).encode()],
        received.append,
        on_drop=lambda: drops.append(None),
    )

    assert [record["frame_counter"] for record in received] == [1, 2]
    assert len(drops) == 1


def test_handler_failure_does_not_stop_the_next_record() -> None:
    received: list[int] = []

    def handle(record: dict[str, Any]) -> None:
        frame_counter = record["frame_counter"]
        if frame_counter == 1:
            raise ValueError("invalid packet")
        received.append(frame_counter)

    consume_messages(
        [encode({"frame_counter": 1}), encode({"frame_counter": 2})], handle
    )

    assert received == [2]


def test_ingress_reconnects_after_disconnect() -> None:
    received: list[dict[str, Any]] = []
    received_two = threading.Event()
    connection_count = 0
    connection_lock = threading.Lock()

    def handler(websocket: ServerConnection) -> None:
        nonlocal connection_count
        with connection_lock:
            connection_count += 1
            frame_counter = connection_count
        websocket.send(encode({"frame_counter": frame_counter}))

    def receive(record: dict[str, Any]) -> None:
        received.append(record)
        if len(received) >= 2:
            received_two.set()

    with serve(handler, "127.0.0.1", 0) as server:
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.start()
        port = server.socket.getsockname()[1]
        try:
            with OpkIngress(receive, port=port, reconnect_delay_seconds=0):
                assert received_two.wait(2)
        finally:
            server.shutdown()
            server_thread.join(timeout=1)

    assert [record["frame_counter"] for record in received[:2]] == [1, 2]


def test_ingress_backs_off_after_repeated_connection_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingress = OpkIngress(lambda record: None, reconnect_delay_seconds=10)
    delays: list[float] = []

    def fail_connect(*args: object, **kwargs: object) -> None:
        raise OSError("OPK unavailable")

    def wait(delay: float) -> bool:
        delays.append(delay)
        if len(delays) == 4:
            ingress._stop.set()
        return False

    monkeypatch.setattr(opk_ingress_module, "connect", fail_connect)
    monkeypatch.setattr(ingress._stop, "wait", wait)

    ingress._run()

    assert delays == [10, 20, 30, 30]


def test_non_positive_record_limit_is_rejected() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        OpkIngress(lambda record: None, max_record_bytes=0)
