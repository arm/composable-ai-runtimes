# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Integration tests for the Python notification-service API."""

import asyncio
import queue
import socket
import subprocess
import sys
import time
from collections.abc import Awaitable, Generator
from concurrent.futures import ThreadPoolExecutor
from types import TracebackType
from typing import Protocol

import grpc
import pytest
import redis
from cairn import Notification, NotificationService, NotificationSubscription
from generated.messaging_pb2 import CairnEvent
from grpc_health.v1 import health, health_pb2, health_pb2_grpc


class UnraisableHookArgs(Protocol):
    object: object
    exc_type: type[BaseException] | None
    exc_value: BaseException | None
    exc_traceback: TracebackType | None


@pytest.fixture
def messaging_health(
    redis_endpoint: str,
) -> Generator[tuple[str, health.HealthServicer], None, None]:
    with ThreadPoolExecutor(max_workers=1) as executor:
        server = grpc.server(executor, options=(("grpc.so_reuseport", 0),))
        servicer = health.HealthServicer()
        servicer.set("", health_pb2.HealthCheckResponse.SERVING)
        health_pb2_grpc.add_HealthServicer_to_server(servicer, server)
        port = server.add_insecure_port("127.0.0.1:0")
        server.start()
        try:
            yield f"http://127.0.0.1:{port}", servicer
        finally:
            server.stop(0).wait()


@pytest.fixture
def messaging_endpoint(messaging_health: tuple[str, health.HealthServicer]) -> str:
    return messaging_health[0]


@pytest.fixture
def redis_endpoint() -> Generator[str, None, None]:
    port = 6379
    with socket.socket() as reservation:
        reservation.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            reservation.bind(("127.0.0.1", port))
        except OSError as error:
            pytest.fail(
                f"notification tests require Redis port {port} to be free: {error}"
            )
    process = subprocess.Popen(
        [
            "redis-server",
            "--bind",
            "127.0.0.1",
            "--port",
            str(port),
            "--save",
            "",
            "--appendonly",
            "no",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    endpoint = f"redis://127.0.0.1:{port}/0"

    try:
        deadline = time.monotonic() + 5
        while True:
            if process.poll() is not None:
                pytest.fail("test Redis server exited before becoming ready")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    pytest.fail("test Redis server did not become ready")
                time.sleep(0.025)
        yield endpoint
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _publish(endpoint: str, channel: str, payload: bytes) -> int:
    client = redis.Redis.from_url(endpoint)
    try:
        event = CairnEvent(
            origin="cairn.test",
            event_type="cairn.test.message",
            topic=channel,
            payload=payload,
        )
        return client.publish(channel, event.SerializeToString())
    finally:
        client.close()


async def _ignore_notification(_notification: Notification) -> None:
    pass


def test_subscribe_returns_notification_subscription(messaging_endpoint: str) -> None:
    async def exercise() -> None:
        async with NotificationService(messaging_endpoint) as service:
            subscription = await service.subscribe(
                "test.notifications", _ignore_notification
            )

            assert isinstance(subscription, NotificationSubscription)

    asyncio.run(exercise())


def test_synchronous_callback_can_return_awaitable(
    redis_endpoint: str, messaging_endpoint: str
) -> None:
    async def exercise(endpoint: str) -> None:
        received: asyncio.Queue[Notification] = asyncio.Queue()

        async def process(notification: Notification) -> None:
            await received.put(notification)

        def receive(notification: Notification) -> Awaitable[None]:
            return process(notification)

        async with NotificationService(messaging_endpoint) as service:
            await service.subscribe("test.notifications", receive)
            await asyncio.to_thread(
                _publish, endpoint, "test.notifications", b"wrapped"
            )
            notification = await asyncio.wait_for(received.get(), timeout=1)

        assert notification.payload == b"wrapped"

    asyncio.run(exercise(redis_endpoint))


def test_callback_receives_notification_with_preserved_fields(
    redis_endpoint: str,
    messaging_endpoint: str,
) -> None:
    async def exercise(endpoint: str) -> None:
        received: asyncio.Queue[Notification] = asyncio.Queue()

        async def receive(notification: Notification) -> None:
            await received.put(notification)

        async with NotificationService(messaging_endpoint) as service:
            await service.subscribe("test.notifications", receive)
            payload = b"\x00\xffbinding payload"
            await asyncio.to_thread(_publish, endpoint, "test.notifications", payload)
            notification = await asyncio.wait_for(received.get(), timeout=1)

            assert isinstance(notification, Notification)
            assert notification.channel == "test.notifications"
            assert notification.payload == payload

    asyncio.run(exercise(redis_endpoint))


def test_unsubscribe_removes_redis_subscription(
    redis_endpoint: str, messaging_endpoint: str
) -> None:
    async def exercise(endpoint: str) -> None:
        async with NotificationService(messaging_endpoint) as service:
            subscription = await service.subscribe(
                "test.notifications", _ignore_notification
            )
            await service.unsubscribe(subscription)
            subscriber_count = await asyncio.to_thread(
                _publish, endpoint, "test.notifications", b"second"
            )
            assert subscriber_count == 0

    asyncio.run(exercise(redis_endpoint))


def test_callback_failure_uses_unraisablehook(
    redis_endpoint: str, messaging_endpoint: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    reported_errors: queue.Queue[UnraisableHookArgs] = queue.Queue()

    def report_unraisable(args: UnraisableHookArgs) -> None:
        reported_errors.put(args)

    monkeypatch.setattr(sys, "unraisablehook", report_unraisable)

    async def failing_handler(_notification: Notification) -> None:
        raise RuntimeError("callback failed")

    async def exercise(endpoint: str) -> None:
        async with NotificationService(messaging_endpoint) as service:
            await service.subscribe("test.notifications", failing_handler)
            await asyncio.to_thread(
                _publish, endpoint, "test.notifications", b"failure"
            )
            error = await asyncio.to_thread(reported_errors.get, True, 1)

        assert error.object is failing_handler
        assert error.exc_type is RuntimeError
        assert str(error.exc_value) == "callback failed"

    asyncio.run(exercise(redis_endpoint))


def test_subscribe_rejects_non_callable(
    redis_endpoint: str, messaging_endpoint: str
) -> None:
    async def exercise(endpoint: str) -> None:
        async with NotificationService(messaging_endpoint) as service:
            with pytest.raises(
                TypeError, match="notification handler must be callable"
            ):
                await service.subscribe("test.notifications", object())  # type: ignore[arg-type]
            subscriber_count = await asyncio.to_thread(
                _publish, endpoint, "test.notifications", b"ignored"
            )
            assert subscriber_count == 0

    asyncio.run(exercise(redis_endpoint))


def test_non_awaitable_callback_result_is_reported_and_delivery_continues(
    redis_endpoint: str, messaging_endpoint: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    reported_errors: queue.Queue[UnraisableHookArgs] = queue.Queue()

    def report_unraisable(args: UnraisableHookArgs) -> None:
        reported_errors.put(args)

    monkeypatch.setattr(sys, "unraisablehook", report_unraisable)

    def invalid_handler(_notification: Notification) -> None:
        return None

    async def exercise(endpoint: str) -> None:
        received: asyncio.Queue[Notification] = asyncio.Queue()

        async def valid_handler(notification: Notification) -> None:
            await received.put(notification)

        async with NotificationService(messaging_endpoint) as service:
            invalid_subscription = await service.subscribe(  # type: ignore[arg-type]
                "test.notifications", invalid_handler
            )
            await asyncio.to_thread(
                _publish, endpoint, "test.notifications", b"invalid"
            )
            error = await asyncio.to_thread(reported_errors.get, True, 1)
            await service.unsubscribe(invalid_subscription)

            await service.subscribe("test.valid", valid_handler)
            await asyncio.to_thread(_publish, endpoint, "test.valid", b"valid")
            notification = await asyncio.wait_for(received.get(), timeout=1)

        assert error.object is invalid_handler
        assert error.exc_type is TypeError
        assert str(error.exc_value) == "notification handler must return an awaitable"
        assert notification.payload == b"valid"

    asyncio.run(exercise(redis_endpoint))


def test_constructor_rejects_redis_url() -> None:
    with pytest.raises(RuntimeError, match="health watch"):
        NotificationService("redis://127.0.0.1:6379/0")


def test_constructor_waits_for_serving(
    redis_endpoint: str, messaging_health: tuple[str, health.HealthServicer]
) -> None:
    endpoint, reporter = messaging_health
    reporter.set("", health_pb2.HealthCheckResponse.NOT_SERVING)
    with redis.Redis.from_url(redis_endpoint) as inspector:
        initial_clients = len(inspector.client_list())
        with ThreadPoolExecutor(max_workers=1) as executor:
            connection = executor.submit(NotificationService, endpoint)
            with pytest.raises(TimeoutError):
                connection.result(timeout=0.1)
            assert len(inspector.client_list()) == initial_clients

            reporter.set("", health_pb2.HealthCheckResponse.SERVING)
            service = connection.result(timeout=2)
            try:
                assert len(inspector.client_list()) == initial_clients + 1
            finally:

                async def close() -> None:
                    await service.close()

                asyncio.run(close())
