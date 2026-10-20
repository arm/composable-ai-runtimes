# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TypedDict, cast

import redis
from google.protobuf.message import DecodeError

from camera_smoke.artifacts import write_command_transcript
from camera_smoke.commands import run_command
from camera_smoke.compose import (
    build_compose_command,
    get_compose_logs,
    has_compose_service_exited,
    is_compose_service_running,
)
from camera_smoke.generated.messaging_pb2 import CairnEvent
from camera_smoke.network import can_connect_to_tcp

REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REDIS_CHANNEL_EVENTS_ENV = "PWC_REDIS_CHANNEL_EVENTS"
DEFAULT_REDIS_CHANNEL = "camera.events"
STARTUP_TIMEOUT_SECONDS = 90
EVENT_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 1
INITIAL_CONNECTED_NOTIFICATION_LOG = "published connected camera notification"
CONNECTED_REDIS_CLIENT_LOG = "connected notifications Redis client"


class CameraEventPayload(TypedDict):
    event_type: str
    id: int
    name: str


class NotificationSmokeError(Exception):
    """Raised for expected camera notification smoke failures."""


def resolve_camera_events_channel_value(value: str | None) -> str:
    return value if value else DEFAULT_REDIS_CHANNEL


def get_configured_camera_events_channel(
    compose_file: Path,
    camera_service_name: str,
    *,
    cwd: Path,
    results_dir: Path,
) -> str:
    result = run_command(
        *build_compose_command(compose_file, "config", "--format", "json"),
        cwd=cwd,
    )
    if result.returncode != 0:
        write_command_transcript(results_dir, "compose-config-json.txt", result)
        raise NotificationSmokeError("failed to inspect camera service Compose config")

    try:
        compose_config = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        write_command_transcript(results_dir, "compose-config-json.txt", result)
        raise NotificationSmokeError(
            f"Compose config returned invalid JSON: {exc}"
        ) from exc

    try:
        env_value = compose_config["services"][camera_service_name]["environment"].get(
            REDIS_CHANNEL_EVENTS_ENV
        )
    except (KeyError, TypeError) as exc:
        raise NotificationSmokeError(
            f"Compose config is missing {camera_service_name} environment"
        ) from exc
    if env_value is not None and not isinstance(env_value, str):
        raise NotificationSmokeError(
            f"Compose config value {REDIS_CHANNEL_EVENTS_ENV} must be a string"
        )

    return resolve_camera_events_channel_value(env_value)


def wait_for_notification_stack_ready(
    compose_file: Path,
    camera_service_name: str,
    messaging_service_name: str,
    *,
    cwd: Path,
    redis_host: str = REDIS_HOST,
    redis_port: int = REDIS_PORT,
    startup_timeout_seconds: float = STARTUP_TIMEOUT_SECONDS,
    poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
) -> tuple[bool, str]:
    deadline = time.monotonic() + startup_timeout_seconds

    while time.monotonic() < deadline:
        logs = get_compose_logs(compose_file, cwd=cwd)
        if has_compose_service_exited(
            compose_file,
            camera_service_name,
            cwd=cwd,
        ) or has_compose_service_exited(
            compose_file,
            messaging_service_name,
            cwd=cwd,
        ):
            return False, "camera notification Compose stack exited during startup"
        if (
            is_compose_service_running(compose_file, camera_service_name, cwd=cwd)
            and is_compose_service_running(
                compose_file,
                messaging_service_name,
                cwd=cwd,
            )
            and can_connect_to_tcp(redis_host, redis_port, timeout_seconds=1)
            and CONNECTED_REDIS_CLIENT_LOG in logs
            and INITIAL_CONNECTED_NOTIFICATION_LOG in logs
        ):
            time.sleep(2)
            return True, "camera notifications observed initial connected camera notification"
        time.sleep(poll_interval_seconds)

    return False, (
        "timed out waiting for camera notifications to publish initial connected "
        "camera notification"
    )


def parse_camera_event_payload(payload: str) -> CameraEventPayload | None:
    try:
        decoded_payload = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if not isinstance(decoded_payload, dict):
        return None

    decoded_payload = cast(dict[str, object], decoded_payload)
    event_type = decoded_payload.get("event_type")
    camera_id = decoded_payload.get("id")
    name = decoded_payload.get("name")
    if not isinstance(event_type, str):
        return None
    if not isinstance(camera_id, int):
        return None
    if not isinstance(name, str):
        return None

    return {
        "event_type": event_type,
        "id": camera_id,
        "name": name,
    }


def decode_camera_event_payload(raw_data: bytes) -> CameraEventPayload | None:
    event = CairnEvent()
    try:
        event.ParseFromString(raw_data)
        payload = event.payload.decode("utf-8")
    except (DecodeError, UnicodeDecodeError):
        return None

    return parse_camera_event_payload(payload)


def get_camera_event_payload(
    pubsub: redis.client.PubSub,
    timeout_seconds: float,
) -> CameraEventPayload | None:
    message = pubsub.get_message(
        ignore_subscribe_messages=True,
        timeout=timeout_seconds,
    )
    if message is None or message.get("type") != "message":
        return None

    raw_data = message.get("data")
    if not isinstance(raw_data, bytes):
        return None

    return decode_camera_event_payload(raw_data)


def wait_for_camera_event(
    pubsub: redis.client.PubSub,
    observed_payloads: list[CameraEventPayload],
    expected_event_type: str,
    *,
    events_channel: str,
    timeout_seconds: float = EVENT_TIMEOUT_SECONDS,
    poll_interval_seconds: float = POLL_INTERVAL_SECONDS,
) -> CameraEventPayload:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        payload = get_camera_event_payload(pubsub, poll_interval_seconds)
        if payload is not None:
            observed_payloads.append(payload)
            if payload["event_type"] == expected_event_type:
                return payload

    raise NotificationSmokeError(
        f"did not observe a {expected_event_type!r} USB camera event on "
        f"{events_channel!r}; "
        f"observed payloads: {observed_payloads}"
    )


def subscribe_to_camera_events(
    pubsub: redis.client.PubSub,
    events_channel: str,
) -> None:
    pubsub.subscribe(events_channel)

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        message = pubsub.get_message(
            ignore_subscribe_messages=False,
            timeout=0.2,
        )
        if message and message.get("type") == "subscribe":
            return

    raise NotificationSmokeError(
        f"timed out subscribing to Redis channel {events_channel!r}"
    )


def redis_client(
    *,
    host: str = REDIS_HOST,
    port: int = REDIS_PORT,
) -> redis.Redis:
    return redis.Redis(
        host=host,
        port=port,
        decode_responses=False,
        socket_connect_timeout=2,
        socket_timeout=2,
    )
