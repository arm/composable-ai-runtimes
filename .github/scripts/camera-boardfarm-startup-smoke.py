#!/usr/bin/env python3
"""Pytest startup smoke probe for the camera board-farm Compose deployment."""

from __future__ import annotations

import json
import os
import re
import socket
import time
from pathlib import Path
from typing import Any, Iterator

import pytest

from camera_smoke.artifacts import (
    write_command_transcript,
    write_text_artifact,
)
from camera_smoke.commands import CommandResult, run_command as run_shell_command
from camera_smoke.time import get_utc_now


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "services" / "camera" / "compose.yaml"
TEST_RESULTS_DIR = REPO_ROOT / "test-results" / "camera-boardfarm-smoke"
SERVICE_NAME = "camera-service"
GRPC_HOST = "127.0.0.1"
GRPC_PORT = 50051
STARTUP_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 2

FAILURE_PATTERN = re.compile(
    r"missing runtime directory|"
    r"PipeWire .*timed out|"
    r"PipeWire .*timeout|"
    r"panic|panicked|"
    r"segmentation fault|"
    r"service process .*exit|"
    r"exited with",
    re.IGNORECASE,
)


def build_compose_command(*args: str) -> list[str]:
    return ["docker", "compose", "-f", str(COMPOSE_FILE), *args]


def run_command(*args: str) -> CommandResult:
    return run_shell_command(*args, cwd=REPO_ROOT)


def get_compose_logs() -> str:
    result = run_command(*build_compose_command("logs", "--no-color"))
    return result.stdout + result.stderr


def get_compose_ps() -> CommandResult:
    return run_command(*build_compose_command("ps", "--all"))


def write_diagnostics(metadata: dict[str, Any]) -> None:
    write_text_artifact(TEST_RESULTS_DIR, "compose.log", get_compose_logs())
    write_command_transcript(TEST_RESULTS_DIR, "compose-ps.txt", get_compose_ps())
    write_text_artifact(
        TEST_RESULTS_DIR, "metadata.json", json.dumps(metadata, indent=2, sort_keys=True)
    )


def cleanup_compose() -> CommandResult:
    return run_command(*build_compose_command("down", "--volumes", "--remove-orphans"))


def is_service_running() -> bool:
    result = run_command(
        *build_compose_command("ps", "--status", "running", "--services")
    )
    if result.returncode != 0:
        return False

    running_services = {
        line.strip() for line in result.stdout.splitlines() if line.strip()
    }
    return SERVICE_NAME in running_services


def has_service_exited() -> bool:
    result = run_command(
        *build_compose_command("ps", "--status", "exited", "--services")
    )
    if result.returncode != 0:
        return False

    exited_services = {
        line.strip() for line in result.stdout.splitlines() if line.strip()
    }
    return SERVICE_NAME in exited_services


def can_connect_to_grpc() -> bool:
    try:
        with socket.create_connection((GRPC_HOST, GRPC_PORT), timeout=2):
            return True
    except OSError:
        return False


def wait_for_startup() -> tuple[bool, str]:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    last_log = ""

    while time.monotonic() < deadline:
        last_log = get_compose_logs()
        if FAILURE_PATTERN.search(last_log):
            return False, "startup logs contain a known failure pattern"
        if has_service_exited():
            return False, "camera-service process exited during startup"
        if (
            is_service_running()
            and can_connect_to_grpc()
            and "starting camera API server" in last_log
        ):
            return True, "camera service is running and accepting TCP connections"
        time.sleep(POLL_INTERVAL_SECONDS)

    return False, "timed out waiting for camera service startup readiness"


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
        write_diagnostics(metadata)
        cleanup_result = cleanup_compose()
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

    logs = get_compose_logs()
    assert "starting camera API server" in logs, (
        "Camera API startup log was not found in Compose logs."
    )
    assert not FAILURE_PATTERN.search(logs), (
        "Compose logs contain a known startup failure pattern."
    )
    assert is_service_running(), "camera-service is not running."
    assert can_connect_to_grpc(), f"Cannot connect to {GRPC_HOST}:{GRPC_PORT}."
