# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Pytest startup smoke probe for the camera board-farm Compose deployment."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from camera_smoke.artifacts import (
    write_command_transcript,
    write_text_artifact,
)
from camera_smoke.camera_service import CAMERA_STARTUP_FAILURE_PATTERN
from camera_smoke.commands import CommandResult
from camera_smoke.commands import run_command as run_shell_command
from camera_smoke.compose import (
    build_compose_command as build_shared_compose_command,
)
from camera_smoke.compose import (
    cleanup_compose,
    get_compose_logs,
    has_compose_service_exited,
    is_compose_service_running,
    write_compose_diagnostics,
)
from camera_smoke.helpers import with_timeout
from camera_smoke.network import can_connect_to_tcp
from camera_smoke.time import get_utc_now

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "services" / "camera" / "compose.yaml"
TEST_RESULTS_DIR = REPO_ROOT / "test-results" / "camera-boardfarm-smoke"
SERVICE_NAME = "camera-service"
GRPC_HOST = "127.0.0.1"
GRPC_PORT = 50051
STARTUP_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 2

def build_compose_command(*args: str) -> list[str]:
    return build_shared_compose_command(COMPOSE_FILE, *args)


def run_command(*args: str) -> CommandResult:
    return run_shell_command(*args, cwd=REPO_ROOT)


@with_timeout(
    STARTUP_TIMEOUT_SECONDS,
    interval_seconds=POLL_INTERVAL_SECONDS,
    on_timeout=lambda: (
        False,
        "timed out waiting for camera service startup readiness",
    ),
)
def wait_for_startup() -> tuple[bool, str] | None:
    logs = get_compose_logs(COMPOSE_FILE, cwd=REPO_ROOT)
    if CAMERA_STARTUP_FAILURE_PATTERN.search(logs):
        return False, "startup logs contain a known failure pattern"
    if has_compose_service_exited(COMPOSE_FILE, SERVICE_NAME, cwd=REPO_ROOT):
        return False, "camera-service process exited during startup"
    if (
        is_compose_service_running(COMPOSE_FILE, SERVICE_NAME, cwd=REPO_ROOT)
        and can_connect_to_tcp(GRPC_HOST, GRPC_PORT)
        and "starting camera API server" in logs
    ):
        return True, "camera service is running and accepting TCP connections"
    return None


@pytest.fixture
def smoke_metadata() -> Iterator[dict[str, Any]]:
    metadata: dict[str, Any] = {
        "started_at": get_utc_now(),
        "compose_project_name": os.environ.get("COMPOSE_PROJECT_NAME"),
        "grpc_target": f"{GRPC_HOST}:{GRPC_PORT}",
    }

    try:
        yield metadata
    finally:
        metadata["finished_at"] = get_utc_now()
        write_compose_diagnostics(
            TEST_RESULTS_DIR, COMPOSE_FILE, metadata, cwd=REPO_ROOT
        )
        cleanup_result = cleanup_compose(COMPOSE_FILE, cwd=REPO_ROOT)
        metadata["cleanup_exit_code"] = cleanup_result.returncode
        if cleanup_result.returncode != 0:
            write_command_transcript(
                TEST_RESULTS_DIR, "compose-cleanup.txt", cleanup_result
            )
        write_text_artifact(
            TEST_RESULTS_DIR,
            "metadata.json",
            json.dumps(metadata, indent=2, sort_keys=True),
        )


def test_camera_boardfarm_compose_config() -> None:
    config_result = run_command(*build_compose_command("config"))
    if config_result.returncode != 0:
        write_command_transcript(TEST_RESULTS_DIR, "compose-config.txt", config_result)
    assert config_result.returncode == 0, (
        "Camera Compose config validation failed. See compose-config.txt."
    )


def test_camera_boardfarm_compose_startup(
    smoke_metadata: dict[str, Any],
) -> None:
    up_result = run_command(*build_compose_command("up", "-d", "--build"))
    smoke_metadata["compose_up_exit_code"] = up_result.returncode
    if up_result.returncode != 0:
        write_command_transcript(TEST_RESULTS_DIR, "compose-up.txt", up_result)
    assert up_result.returncode == 0, (
        "Camera Compose startup command failed. See compose-up.txt."
    )

    ready, reason = wait_for_startup()
    smoke_metadata["startup_ready"] = ready
    smoke_metadata["startup_result"] = reason
    assert ready, reason

    logs = get_compose_logs(COMPOSE_FILE, cwd=REPO_ROOT)
    assert "starting camera API server" in logs, (
        "Camera API startup log was not found in Compose logs."
    )
    assert not CAMERA_STARTUP_FAILURE_PATTERN.search(logs), (
        "Compose logs contain a known startup failure pattern."
    )
    assert is_compose_service_running(COMPOSE_FILE, SERVICE_NAME, cwd=REPO_ROOT), (
        "camera-service is not running."
    )
    assert can_connect_to_tcp(GRPC_HOST, GRPC_PORT), (
        f"Cannot connect to {GRPC_HOST}:{GRPC_PORT}."
    )
