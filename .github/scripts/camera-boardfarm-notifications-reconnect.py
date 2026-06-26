#!/usr/bin/env python3
"""Pytest Redis reconnect probe for camera notifications on the board farm."""

from __future__ import annotations

import json
import os
import socket
import time
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import cast

import pytest

from camera_smoke.artifacts import write_command_transcript, write_text_artifact
from camera_smoke.commands import run_command
from camera_smoke.compose import (
    build_compose_command,
    cleanup_compose,
    get_compose_logs,
    is_compose_service_running,
    write_compose_diagnostics,
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
from camera_smoke.notifications import (
    DEFAULT_REDIS_CHANNEL,
    EVENT_TIMEOUT_SECONDS,
    POLL_INTERVAL_SECONDS,
    REDIS_HOST,
    REDIS_PORT,
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
TEST_RESULTS_DIR = (
    REPO_ROOT / "test-results" / "camera-boardfarm-notifications" / "reconnect"
)
SERVICE_NAME = "camera-service"
MESSAGING_SERVICE_NAME = "messaging-service"
PUBLISH_DISCONNECTED_FAILURE_LOG = (
    "failed to publish disconnected camera notification"
)
RECONNECTING_REDIS_LOG = "reconnecting notifications Redis client"
RECONNECTED_REDIS_LOG = "reconnected notifications Redis client"
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
    notifications_pid_before_failure: str = ""
    notifications_pid_after_reconnect: str = ""
    publish_failure_log_observed: bool = False
    publish_failure_log_result: str = "not_started"
    reconnecting_log_observed: bool = False
    reconnecting_log_result: str = "not_started"
    reconnected_log_observed: bool = False
    reconnected_log_result: str = "not_started"
    later_event_publish_observed: bool = False
    later_event_publish_result: str = "not_started"
    compose_up_exit_code: int = -1
    startup_ready: bool = False
    startup_result: str = ""
    hotplug_cleanup_status: str = "not_started"
    hotplug_cleanup_error: str = ""
    cleanup_exit_code: int = -1

    def to_json_dict(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))


def wait_for_compose_log_after_baseline(
    expected_message: str,
    baseline: str,
    *,
    timeout_seconds: float,
) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        logs = get_compose_logs(COMPOSE_FILE, cwd=REPO_ROOT)
        logs_after_baseline = logs[len(baseline) :] if logs.startswith(baseline) else logs
        if expected_message in logs_after_baseline:
            return True, f"observed {expected_message!r}"
        time.sleep(POLL_INTERVAL_SECONDS)

    return False, f"timed out waiting for {expected_message!r}"


def read_notifications_pid(transcript_name: str) -> str:
    result = run_command(
        *build_compose_command(
            COMPOSE_FILE,
            "exec",
            "-T",
            SERVICE_NAME,
            "sh",
            "-c",
            (
                "for proc in /proc/[0-9]*; do "
                'test "$(cat "$proc/comm" 2>/dev/null)" = notifications '
                '&& basename "$proc"; '
                "done; exit 0"
            ),
        ),
        cwd=REPO_ROOT,
    )
    write_command_transcript(TEST_RESULTS_DIR, transcript_name, result)
    assert result.returncode == 0, (
        f"failed to read notifications process PID; see {transcript_name}"
    )

    pids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert len(pids) == 1, (
        f"expected exactly one notifications process PID inside {SERVICE_NAME}, "
        f"got {pids}"
    )
    return pids[0]


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


def wait_for_tcp_available(
    host: str,
    port: int,
    *,
    timeout_seconds: float,
    poll_interval_seconds: float = 1,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if can_connect_to_tcp(host, port, timeout_seconds=1):
            return True
        time.sleep(poll_interval_seconds)
    return can_connect_to_tcp(host, port, timeout_seconds=1)


def stop_messaging_service() -> None:
    result = run_command(
        *build_compose_command(COMPOSE_FILE, "stop", MESSAGING_SERVICE_NAME),
        cwd=REPO_ROOT,
    )
    write_command_transcript(TEST_RESULTS_DIR, "redis-stop.txt", result)
    assert result.returncode == 0, (
        f"failed to stop {MESSAGING_SERVICE_NAME}; see redis-stop.txt"
    )


def start_messaging_service(
    *,
    require_success: bool = True,
) -> None:
    result = run_command(
        *build_compose_command(COMPOSE_FILE, "start", MESSAGING_SERVICE_NAME),
        cwd=REPO_ROOT,
    )
    write_command_transcript(TEST_RESULTS_DIR, "redis-start.txt", result)
    if require_success:
        assert result.returncode == 0, (
            f"failed to start {MESSAGING_SERVICE_NAME}; see redis-start.txt"
        )


def trigger_disconnect_while_redis_is_down(
    metadata: NotificationMetadata,
    target: UsbCameraTarget,
    logs_baseline: str,
) -> None:
    stop_messaging_service()

    unbind_usb_camera(
        target,
        cwd=REPO_ROOT,
        write_command_transcript=write_hotplug_command_transcript,
    )

    metadata.publish_failure_log_result = (
        f"waiting for {PUBLISH_DISCONNECTED_FAILURE_LOG!r}"
    )
    observed, reason = wait_for_compose_log_after_baseline(
        PUBLISH_DISCONNECTED_FAILURE_LOG,
        logs_baseline,
        timeout_seconds=EVENT_TIMEOUT_SECONDS,
    )
    metadata.publish_failure_log_observed = observed
    metadata.publish_failure_log_result = reason
    assert observed, reason

    metadata.reconnecting_log_result = f"waiting for {RECONNECTING_REDIS_LOG!r}"
    observed, reason = wait_for_compose_log_after_baseline(
        RECONNECTING_REDIS_LOG,
        logs_baseline,
        timeout_seconds=EVENT_TIMEOUT_SECONDS,
    )
    metadata.reconnecting_log_observed = observed
    metadata.reconnecting_log_result = reason
    assert observed, reason


def restart_redis_and_wait_for_notification_reconnect(
    metadata: NotificationMetadata,
    logs_baseline: str,
) -> None:
    start_messaging_service()
    redis_ready_after_restart = wait_for_tcp_available(
        REDIS_HOST,
        REDIS_PORT,
        timeout_seconds=30,
        poll_interval_seconds=POLL_INTERVAL_SECONDS,
    )
    if not redis_ready_after_restart:
        metadata.result = "redis_restart_readiness_failed"
        pytest.fail(f"{MESSAGING_SERVICE_NAME} did not become reachable after restart")

    metadata.reconnected_log_result = f"waiting for {RECONNECTED_REDIS_LOG!r}"
    observed, reason = wait_for_compose_log_after_baseline(
        RECONNECTED_REDIS_LOG,
        logs_baseline,
        timeout_seconds=EVENT_TIMEOUT_SECONDS,
    )
    metadata.reconnected_log_observed = observed
    metadata.reconnected_log_result = reason
    assert observed, reason


def verify_notifications_process_did_not_restart(
    metadata: NotificationMetadata,
) -> None:
    metadata.notifications_pid_after_reconnect = read_notifications_pid(
        "notifications-pid-after-reconnect.txt"
    )
    if (
        metadata.notifications_pid_after_reconnect
        != metadata.notifications_pid_before_failure
    ):
        metadata.result = "notifications_process_restarted"
        pytest.fail("notifications process restarted during Redis reconnect probe")


def verify_later_connected_event_is_published(
    metadata: NotificationMetadata,
    target: UsbCameraTarget,
    events_channel: str,
) -> None:
    observed_payloads: list[CameraEventPayload] = []

    with redis_client() as client, client.pubsub() as subscription:
        subscribe_to_camera_events(subscription, events_channel)
        bind_usb_camera(
            target,
            cwd=REPO_ROOT,
            write_command_transcript=write_hotplug_command_transcript,
        )

        metadata.later_event_publish_result = (
            "waiting for connected Redis event after Redis reconnect"
        )
        connected_payload = wait_for_camera_event(
            subscription,
            observed_payloads,
            "connected",
            events_channel=events_channel,
        )
        metadata.later_event_publish_observed = True
        metadata.later_event_publish_result = (
            "observed connected Redis event after Redis reconnect"
        )

    assert connected_payload["event_type"] == "connected"


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
        write_compose_diagnostics(
            TEST_RESULTS_DIR,
            COMPOSE_FILE,
            notification_metadata.to_json_dict(),
            cwd=REPO_ROOT,
        )
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


@pytest.fixture
def messaging_service_cleanup(
    compose_stack: NotificationMetadata,
) -> Iterator[None]:
    yield
    if not is_compose_service_running(
        COMPOSE_FILE,
        MESSAGING_SERVICE_NAME,
        cwd=REPO_ROOT,
    ):
        start_messaging_service(require_success=False)


def test_publish_failure_reconnects_and_later_camera_event_is_published(
    compose_stack: NotificationMetadata,
    messaging_service_cleanup: None,
    usb_camera_target: UsbCameraTarget,
) -> None:
    metadata = compose_stack
    metadata.result = "reconnect_publish_started"
    events_channel = metadata.redis_channel
    target = usb_camera_target
    logs_baseline = get_compose_logs(COMPOSE_FILE, cwd=REPO_ROOT)
    metadata.notifications_pid_before_failure = read_notifications_pid(
        "notifications-pid-before-failure.txt"
    )

    trigger_disconnect_while_redis_is_down(
        metadata,
        target,
        logs_baseline,
    )
    restart_redis_and_wait_for_notification_reconnect(
        metadata,
        logs_baseline,
    )
    verify_notifications_process_did_not_restart(metadata)
    verify_later_connected_event_is_published(metadata, target, events_channel)

    metadata.result = "passed"
