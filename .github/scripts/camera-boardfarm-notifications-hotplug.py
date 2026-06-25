#!/usr/bin/env python3
"""Pytest hotplug probe for Redis camera notifications on the board farm."""

from __future__ import annotations

import json
import os
import socket
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import cast

import pytest

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
from camera_smoke.notifications import (
    DEFAULT_REDIS_CHANNEL,
    CameraEventPayload,
    get_configured_camera_events_channel,
    redis_client,
    subscribe_to_camera_events,
    wait_for_camera_event,
    wait_for_notification_stack_ready,
)
from camera_smoke.time import get_utc_now


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "services" / "compose.yaml"
TEST_RESULTS_DIR = REPO_ROOT / "test-results" / "camera-boardfarm-notifications"
SERVICE_NAME = "camera-service"
MESSAGING_SERVICE_NAME = "messaging-service"
write_hotplug_command_transcript: CommandTranscriptWriter = partial(
    write_command_transcript,
    TEST_RESULTS_DIR,
)


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


def get_metadata_redis_channel(metadata: NotificationMetadata) -> str:
    channel = metadata.redis_channel
    if not channel:
        raise _ScriptError("missing resolved Redis camera events channel")
    return channel


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

    ready, reason = wait_for_notification_stack_ready(
        COMPOSE_FILE,
        SERVICE_NAME,
        MESSAGING_SERVICE_NAME,
        cwd=REPO_ROOT,
    )
    metadata.startup_ready = ready
    metadata.startup_result = reason
    assert ready, reason
    metadata.redis_channel = get_configured_camera_events_channel(
        COMPOSE_FILE,
        SERVICE_NAME,
        cwd=REPO_ROOT,
        results_dir=TEST_RESULTS_DIR,
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
