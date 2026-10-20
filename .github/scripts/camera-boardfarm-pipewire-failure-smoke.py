# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Pytest PipeWire failure probe for the camera board-farm Compose deployment."""

from __future__ import annotations

import json
import os
import re
import socket
from collections.abc import Iterator
from pathlib import Path

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
from camera_smoke.grpc import classify_grpcurl_failure, summarize_command_output
from camera_smoke.helpers import with_timeout
from camera_smoke.network import can_connect_to_tcp
from camera_smoke.time import get_utc_now

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "services" / "camera" / "compose.yaml"
TEST_RESULTS_DIR = REPO_ROOT / "test-results" / "camera-boardfarm-pipewire-failure"
SERVICE_NAME = "camera-service"
GRPC_HOST = "127.0.0.1"
GRPC_PORT = 50051
GRPC_TARGET = f"{GRPC_HOST}:{GRPC_PORT}"
GRPCURL_BINARY_ENV = "GRPCURL_BIN"
GRPCURL_DEFAULT_BINARY = "grpcurl"
CAMERA_SERVICE_PROTO = REPO_ROOT / "services" / "camera" / "proto" / "camera_service.proto"
CAMERA_SERVICE_PROTO_ARG = str(CAMERA_SERVICE_PROTO.relative_to(REPO_ROOT))
LIST_CAMERAS_METHOD = "camera.pipewire.v1.CameraService/ListCameras"
STARTUP_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 2
PIPEWIRE_SOCKET_PATH = "/run/pipewire/pipewire-0"
PIPEWIRE_LOG_PATTERN = re.compile(
    r"PipeWire|WirePlumber|snapshot|runtime directory|"
    r"failed to connect to PipeWire|failed to get PipeWire registry|"
    r"failed to create PipeWire",
    re.IGNORECASE | re.DOTALL,
)
JsonObject = dict[str, object]


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


def fail_with_result(metadata: JsonObject, result: str, message: str) -> None:
    metadata["result"] = result
    pytest.fail(message)


@pytest.fixture(scope="module")
def metadata() -> Iterator[JsonObject]:
    metadata: JsonObject = {
        "started_at": get_utc_now(),
        "compose_file": str(COMPOSE_FILE.relative_to(REPO_ROOT)),
        "compose_project_name": os.environ.get("COMPOSE_PROJECT_NAME"),
        "grpcurl_binary": os.environ.get(GRPCURL_BINARY_ENV, GRPCURL_DEFAULT_BINARY),
        "grpc_target": GRPC_TARGET,
        "grpc_proto": CAMERA_SERVICE_PROTO_ARG,
        "board_id": (
            os.environ.get("CAMERA_BOARDFARM_BOARD_ID")
            or os.environ.get("BOARD_ID")
            or os.environ.get("RUNNER_NAME")
            or socket.gethostname()
        ),
        "hostname": socket.gethostname(),
        "runner_name": os.environ.get("RUNNER_NAME"),
        "candidate_sha": os.environ.get("GITHUB_SHA"),
        "workflow_name": os.environ.get("GITHUB_WORKFLOW"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "image_os": os.environ.get("ImageOS"),
        "image_version": os.environ.get("ImageVersion"),
        "pipewire_socket_path": PIPEWIRE_SOCKET_PATH,
        "result": "started",
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


def test_camera_boardfarm_pipewire_failure_smoke(metadata: JsonObject) -> None:
    up_result = run_command(*build_compose_command("up", "-d", "--build"))
    metadata["compose_up_exit_code"] = up_result.returncode
    if up_result.returncode != 0:
        write_command_transcript(TEST_RESULTS_DIR, "compose-up.txt", up_result)
        fail_with_result(
            metadata,
            "compose_start_failed",
            "Camera Compose startup command failed. See compose-up.txt.",
        )

    ready, startup_message = wait_for_startup()
    metadata["startup_ready"] = ready
    metadata["startup_result"] = startup_message
    if not ready:
        fail_with_result(metadata, "startup_readiness_failed", startup_message)

    injection_result = run_command(
        *build_compose_command(
            "exec",
            "-T",
            SERVICE_NAME,
            "chmod",
            "000",
            PIPEWIRE_SOCKET_PATH,
        )
    )
    metadata["pipewire_socket_path"] = PIPEWIRE_SOCKET_PATH
    metadata["pipewire_failure_injection"] = "chmod 000 pipewire socket"
    metadata["pipewire_failure_injection_exit_code"] = injection_result.returncode
    if injection_result.returncode != 0:
        write_command_transcript(
            TEST_RESULTS_DIR, "pipewire-failure-injection.txt", injection_result
        )
        fail_with_result(
            metadata,
            "pipewire_failure_injection_failed",
            "Failed to make PipeWire unavailable. "
            "See pipewire-failure-injection.txt.",
        )

    grpcurl_binary = os.environ.get(GRPCURL_BINARY_ENV, GRPCURL_DEFAULT_BINARY)
    grpcurl_result = run_command(
        grpcurl_binary,
        "-plaintext",
        "-proto",
        CAMERA_SERVICE_PROTO_ARG,
        "-d",
        "{}",
        GRPC_TARGET,
        LIST_CAMERAS_METHOD,
    )
    grpc_output = f"{grpcurl_result.stdout}\n{grpcurl_result.stderr}"
    grpc_failure_result = classify_grpcurl_failure(grpcurl_result)
    metadata["list_cameras_exit_code"] = grpcurl_result.returncode
    metadata["list_cameras_failure_result"] = grpc_failure_result
    metadata["list_cameras_unavailable"] = (
        grpc_failure_result == "pipewire_discovery_failed"
    )
    metadata["list_cameras_mentions_pipewire"] = (
        PIPEWIRE_LOG_PATTERN.search(grpc_output) is not None
    )
    write_command_transcript(TEST_RESULTS_DIR, "list-cameras-command.txt", grpcurl_result)
    write_text_artifact(TEST_RESULTS_DIR, "list-cameras.stdout", grpcurl_result.stdout)

    if grpcurl_result.returncode == 0:
        fail_with_result(
            metadata,
            "list_cameras_unexpectedly_succeeded",
            "list_cameras unexpectedly succeeded after PipeWire failure injection.",
        )
    if grpc_failure_result != "pipewire_discovery_failed":
        fail_with_result(
            metadata,
            "list_cameras_missing_unavailable",
            "list_cameras did not return gRPC UNAVAILABLE. "
            "See list-cameras-command.txt.\n"
            f"{summarize_command_output(grpcurl_result)}",
        )
    if PIPEWIRE_LOG_PATTERN.search(grpc_output) is None:
        fail_with_result(
            metadata,
            "list_cameras_missing_pipewire_failure",
            "list_cameras failure did not mention PipeWire. "
            "See list-cameras-command.txt.",
        )

    logs = get_compose_logs(COMPOSE_FILE, cwd=REPO_ROOT)
    write_text_artifact(TEST_RESULTS_DIR, "compose-actionable-log-scan.txt", logs)
    metadata["actionable_pipewire_logs_observed"] = (
        "failed to list cameras" in logs and PIPEWIRE_LOG_PATTERN.search(logs) is not None
    )
    if not metadata["actionable_pipewire_logs_observed"]:
        fail_with_result(
            metadata,
            "compose_logs_missing_pipewire_details",
            "Compose logs did not contain actionable PipeWire failure details.",
        )
    metadata["result"] = "passed"
