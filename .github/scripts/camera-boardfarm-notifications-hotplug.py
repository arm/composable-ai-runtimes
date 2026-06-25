#!/usr/bin/env python3
"""Pytest hotplug probe for Redis camera notifications on the board farm."""

from __future__ import annotations

import json
import os
import socket
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import TypedDict, cast

import pytest
import redis

from camera_smoke.artifacts import (
    write_command_transcript,
    write_text_artifact,
)
from camera_smoke.commands import run_command
from camera_smoke.compose import (
    build_compose_command,
    cleanup_compose,
    get_compose_logs,
    get_compose_ps,
    has_compose_service_exited,
    is_compose_service_running,
)
from camera_smoke.hotplug import (
    CommandTranscriptWriter,
    HotplugError,
    UsbCameraTarget,
    bind_usb_camera,
    ensure_usb_camera_bound,
    select_usb_camera_target,
    unbind_usb_camera,
)
from camera_smoke.network import can_connect_to_tcp
from camera_smoke.time import get_utc_now


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "services" / "compose.yaml"
TEST_RESULTS_DIR = REPO_ROOT / "test-results" / "camera-boardfarm-notifications"
SERVICE_NAME = "camera-service"
MESSAGING_SERVICE_NAME = "messaging-service"
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REDIS_CHANNEL_EVENTS_ENV = "PWC_REDIS_CHANNEL_EVENTS"
DEFAULT_REDIS_CHANNEL = "camera.events"
STARTUP_TIMEOUT_SECONDS = 90
EVENT_TIMEOUT_SECONDS = 30
POLL_INTERVAL_SECONDS = 1
INITIAL_CONNECTED_NOTIFICATION_LOG = "published connected camera notification"
write_hotplug_command_transcript: CommandTranscriptWriter = partial(
    write_command_transcript,
    TEST_RESULTS_DIR,
)


class CameraEventPayload(TypedDict):
    event_type: str
    id: int
    name: str


@dataclass
class NotificationMetadata:
    started_at: str
    compose_file: str
    compose_project_name: str
    hostname: str
    result: str = "started"
    finished_at: str = ""
    redis_channel: str = DEFAULT_REDIS_CHANNEL
    hotplug_device_path: str = ""
    compose_up_exit_code: int = -1
    startup_ready: bool = False
    startup_result: str = ""
    hotplug_cleanup_status: str = "not_started"
    hotplug_cleanup_error: str = ""
    cleanup_exit_code: int = -1

    def to_json_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


class _ScriptError(Exception):
    """Raised for expected script failures."""


def resolve_camera_events_channel_value(value: str | None) -> str:
    return value if value else DEFAULT_REDIS_CHANNEL


def get_configured_camera_events_channel(metadata: NotificationMetadata) -> str:
    result = run_command(
        *build_compose_command(COMPOSE_FILE, "config", "--format", "json"),
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        write_command_transcript(TEST_RESULTS_DIR, "compose-config-json.txt", result)
        raise _ScriptError("failed to inspect camera service Compose config")

    try:
        compose_config = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        write_command_transcript(TEST_RESULTS_DIR, "compose-config-json.txt", result)
        raise _ScriptError(f"Compose config returned invalid JSON: {exc}") from exc

    try:
        env_value = compose_config["services"][SERVICE_NAME]["environment"].get(
            REDIS_CHANNEL_EVENTS_ENV
        )
    except (KeyError, TypeError) as exc:
        raise _ScriptError(
            f"Compose config is missing {SERVICE_NAME} environment"
        ) from exc
    if env_value is not None and not isinstance(env_value, str):
        raise _ScriptError(
            f"Compose config value {REDIS_CHANNEL_EVENTS_ENV} must be a string"
        )

    events_channel = resolve_camera_events_channel_value(env_value)
    return events_channel


def get_metadata_redis_channel(metadata: NotificationMetadata) -> str:
    channel = metadata.redis_channel
    if not channel:
        raise _ScriptError("missing resolved Redis camera events channel")
    return channel


def wait_for_stack_ready() -> tuple[bool, str]:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        logs = get_compose_logs(COMPOSE_FILE, cwd=REPO_ROOT)
        if has_compose_service_exited(
            COMPOSE_FILE,
            SERVICE_NAME,
            cwd=REPO_ROOT,
        ) or has_compose_service_exited(
            COMPOSE_FILE,
            MESSAGING_SERVICE_NAME,
            cwd=REPO_ROOT,
        ):
            return False, "camera notification Compose stack exited during startup"
        if (
            is_compose_service_running(COMPOSE_FILE, SERVICE_NAME, cwd=REPO_ROOT)
            and is_compose_service_running(
                COMPOSE_FILE,
                MESSAGING_SERVICE_NAME,
                cwd=REPO_ROOT,
            )
            and can_connect_to_tcp(REDIS_HOST, REDIS_PORT, timeout_seconds=1)
            and "connected notifications Redis client" in logs
            and INITIAL_CONNECTED_NOTIFICATION_LOG in logs
        ):
            time.sleep(2)
            return True, "camera notifications observed initial connected camera notification"
        time.sleep(POLL_INTERVAL_SECONDS)

    return False, (
        "timed out waiting for camera notifications to publish initial connected "
        "camera notification"
    )


def write_diagnostics(metadata: NotificationMetadata) -> None:
    write_text_artifact(
        TEST_RESULTS_DIR, "compose.log", get_compose_logs(COMPOSE_FILE, cwd=REPO_ROOT)
    )
    write_command_transcript(
        TEST_RESULTS_DIR,
        "compose-ps.txt",
        get_compose_ps(COMPOSE_FILE, cwd=REPO_ROOT),
    )
    write_text_artifact(
        TEST_RESULTS_DIR,
        "metadata.json",
        json.dumps(metadata.to_json_dict(), indent=2, sort_keys=True),
    )


def start_compose_stack(metadata: NotificationMetadata) -> None:
    config_result = run_command(
        *build_compose_command(COMPOSE_FILE, "config"),
        cwd=REPO_ROOT,
    )
    if config_result.returncode != 0:
        write_command_transcript(TEST_RESULTS_DIR, "compose-config.txt", config_result)
    assert config_result.returncode == 0, (
        "Camera notification Compose config validation failed. See compose-config.txt."
    )

    up_result = run_command(
        *build_compose_command(COMPOSE_FILE, "up", "-d", "--build"),
        cwd=REPO_ROOT,
    )
    metadata.compose_up_exit_code = up_result.returncode
    if up_result.returncode != 0:
        write_command_transcript(TEST_RESULTS_DIR, "compose-up.txt", up_result)
    assert up_result.returncode == 0, (
        "Camera notification Compose startup command failed. See compose-up.txt."
    )

    ready, reason = wait_for_stack_ready()
    metadata.startup_ready = ready
    metadata.startup_result = reason
    assert ready, reason
    metadata.redis_channel = get_configured_camera_events_channel(metadata)


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
    if not isinstance(raw_data, str):
        return None

    return parse_camera_event_payload(raw_data)


def wait_for_camera_event(
    pubsub: redis.client.PubSub,
    observed_payloads: list[CameraEventPayload],
    expected_event_type: str,
    *,
    events_channel: str,
    timeout_seconds: float = EVENT_TIMEOUT_SECONDS,
) -> CameraEventPayload:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        payload = get_camera_event_payload(pubsub, POLL_INTERVAL_SECONDS)
        if payload is not None:
            observed_payloads.append(payload)
            # The board farm concurrency group gives this job exclusive camera
            # setup access, so the only matching hotplug event expected during
            # this subscription window is the intentional unbind/rebind action.
            if payload["event_type"] == expected_event_type:
                return payload

    pytest.fail(
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

    pytest.fail(f"timed out subscribing to Redis channel {events_channel!r}")


def redis_client() -> redis.Redis:
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


@pytest.fixture(scope="module")
def notification_metadata() -> NotificationMetadata:
    return NotificationMetadata(
        started_at=get_utc_now(),
        compose_file=str(COMPOSE_FILE.relative_to(REPO_ROOT)),
        compose_project_name=os.environ.get("COMPOSE_PROJECT_NAME", ""),
        hostname=socket.gethostname(),
    )


@pytest.fixture(scope="module")
def compose_stack(
    notification_metadata: NotificationMetadata,
) -> Iterator[NotificationMetadata]:
    try:
        start_compose_stack(notification_metadata)
        yield notification_metadata
    finally:
        notification_metadata.finished_at = get_utc_now()
        write_diagnostics(notification_metadata)
        cleanup_result = cleanup_compose(COMPOSE_FILE, cwd=REPO_ROOT)
        notification_metadata.cleanup_exit_code = cleanup_result.returncode
        if cleanup_result.returncode != 0:
            write_command_transcript(
                TEST_RESULTS_DIR,
                "compose-cleanup.txt",
                cleanup_result,
            )
        write_text_artifact(
            TEST_RESULTS_DIR,
            "metadata.json",
            json.dumps(notification_metadata.to_json_dict(), indent=2, sort_keys=True),
        )


@pytest.fixture(scope="module")
def usb_camera_target(
    compose_stack: NotificationMetadata,
) -> Iterator[UsbCameraTarget]:
    try:
        target = select_usb_camera_target()
        compose_stack.hotplug_device_path = str(target.device_path)
    except HotplugError as exc:
        compose_stack.result = "hotplug_target_selection_failed"
        pytest.fail(str(exc))

    yield target
    cleanup_result = ensure_usb_camera_bound(
        target,
        cwd=REPO_ROOT,
        write_command_transcript=write_hotplug_command_transcript,
    )
    compose_stack.hotplug_cleanup_status = cleanup_result.status
    compose_stack.hotplug_cleanup_error = cleanup_result.error


def test_usb_camera_unbind_rebind_publishes_disconnect_and_connect_events(
    compose_stack: NotificationMetadata,
    usb_camera_target: UsbCameraTarget,
) -> None:
    metadata = compose_stack
    events_channel = get_metadata_redis_channel(metadata)
    target = usb_camera_target
    observed_payloads: list[CameraEventPayload] = []

    with redis_client() as client, client.pubsub() as subscription:
        subscribe_to_camera_events(subscription, events_channel)
        unbind_usb_camera(
            target,
            cwd=REPO_ROOT,
            write_command_transcript=write_hotplug_command_transcript,
        )
        disconnected_payload = wait_for_camera_event(
            subscription,
            observed_payloads,
            "disconnected",
            events_channel=events_channel,
        )

        bind_usb_camera(
            target,
            cwd=REPO_ROOT,
            write_command_transcript=write_hotplug_command_transcript,
        )
        connected_payload = wait_for_camera_event(
            subscription,
            observed_payloads,
            "connected",
            events_channel=events_channel,
        )

    assert disconnected_payload["event_type"] == "disconnected"
    assert connected_payload["event_type"] == "connected"
    metadata.result = "passed"
