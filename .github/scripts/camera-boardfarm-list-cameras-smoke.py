#!/usr/bin/env python3
"""Pytest camera discovery smoke probe for the board-farm Compose deployment."""

from __future__ import annotations

import json
import os
import re
import socket
import time
from pathlib import Path
from typing import Iterator, TypedDict

import pytest

from camera_smoke.artifacts import (
    write_command_transcript,
    write_text_artifact,
)
from camera_smoke.camera_service import CAMERA_STARTUP_FAILURE_PATTERN
from camera_smoke.commands import CommandResult, run_command as run_shell_command
from camera_smoke.compose import (
    build_compose_command as build_shared_compose_command,
    cleanup_compose,
    get_compose_logs,
    get_compose_ps,
    has_compose_service_exited,
    is_compose_service_running,
)
from camera_smoke.network import can_connect_to_tcp
from camera_smoke.time import get_utc_now


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "services" / "camera" / "compose.yaml"
TEST_RESULTS_DIR = REPO_ROOT / "test-results" / "camera-boardfarm-list-cameras-smoke"
SERVICE_NAME = "camera-service"
GRPC_HOST = "127.0.0.1"
GRPC_PORT = 50051
STARTUP_TIMEOUT_SECONDS = 60
CAMERA_DISCOVERY_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 2
GRPC_TARGET = f"{GRPC_HOST}:{GRPC_PORT}"
GRPCURL_BINARY_ENV = "GRPCURL_BIN"
GRPCURL_DEFAULT_BINARY = "grpcurl"
CAMERA_SERVICE_PROTO = REPO_ROOT / "services" / "camera" / "proto" / "camera_service.proto"
CAMERA_SERVICE_PROTO_ARG = str(CAMERA_SERVICE_PROTO.relative_to(REPO_ROOT))
LIST_CAMERAS_METHOD = "camera.pipewire.v1.CameraService/list_cameras"

GRPC_CONNECTION_PATTERN = re.compile(
    r"failed to connect:|transport error|connection refused|tcp connect error|"
    r"error trying to connect|connect error|failed to dial target host|"
    r"context deadline exceeded|connection reset by peer|broken pipe",
    re.IGNORECASE,
)
PIPEWIRE_DISCOVERY_PATTERN = re.compile(
    r"Unavailable|UNAVAILABLE|Code:\s*Unavailable|code = Unavailable|PipeWire|"
    r"WirePlumber|snapshot|runtime directory",
    re.IGNORECASE | re.DOTALL,
)
RETRYABLE_DISCOVERY_RESULTS = {
    "grpc_connection_failed",
    "pipewire_discovery_failed",
}
COMMAND_OUTPUT_SUMMARY_LIMIT = 1000
JsonObject = dict[str, object]


class CameraJson(TypedDict):
    name: str


class ListCamerasJson(TypedDict):
    cameras: list[CameraJson]


def build_compose_command(*args: str) -> list[str]:
    return build_shared_compose_command(COMPOSE_FILE, *args)


def run_command(*args: str) -> CommandResult:
    return run_shell_command(*args, cwd=REPO_ROOT)


def write_diagnostics(metadata: JsonObject) -> None:
    write_text_artifact(
        TEST_RESULTS_DIR, "compose.log", get_compose_logs(COMPOSE_FILE, cwd=REPO_ROOT)
    )
    write_command_transcript(
        TEST_RESULTS_DIR,
        "compose-ps.txt",
        get_compose_ps(COMPOSE_FILE, cwd=REPO_ROOT),
    )
    write_text_artifact(
        TEST_RESULTS_DIR, "metadata.json", json.dumps(metadata, indent=2, sort_keys=True)
    )


def wait_for_startup() -> tuple[bool, str]:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
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
        time.sleep(POLL_INTERVAL_SECONDS)

    return False, "timed out waiting for camera service startup readiness"


def build_initial_metadata() -> JsonObject:
    return {
        "started_at": get_utc_now(),
        "compose_file": str(COMPOSE_FILE.relative_to(REPO_ROOT)),
        "compose_project_name": os.environ.get("COMPOSE_PROJECT_NAME"),
        "expected_camera_name_pattern": os.environ.get(
            "CAMERA_BOARDFARM_EXPECTED_CAMERA_NAME_PATTERN"
        ),
        "grpcurl_binary": os.environ.get(GRPCURL_BINARY_ENV, GRPCURL_DEFAULT_BINARY),
        "grpc_target": GRPC_TARGET,
        "grpc_proto": CAMERA_SERVICE_PROTO_ARG,
        "hostname": socket.gethostname(),
        "result": "started",
    }


def run_grpcurl_list_cameras() -> CommandResult:
    grpcurl_binary = os.environ.get(GRPCURL_BINARY_ENV, GRPCURL_DEFAULT_BINARY)
    return run_command(
        grpcurl_binary,
        "-plaintext",
        "-proto",
        CAMERA_SERVICE_PROTO_ARG,
        "-d",
        "{}",
        GRPC_TARGET,
        LIST_CAMERAS_METHOD,
    )


def classify_grpcurl_failure(result: CommandResult) -> str:
    output = f"{result.stdout}\n{result.stderr}"
    if GRPC_CONNECTION_PATTERN.search(output):
        return "grpc_connection_failed"
    if PIPEWIRE_DISCOVERY_PATTERN.search(output):
        return "pipewire_discovery_failed"
    return "grpcurl_failed"


def summarize_command_output(result: CommandResult) -> str:
    output = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}".strip()
    if len(output) <= COMMAND_OUTPUT_SUMMARY_LIMIT:
        return output
    return f"{output[:COMMAND_OUTPUT_SUMMARY_LIMIT]}...<truncated>"


def parse_camera(value: object) -> CameraJson:
    if not isinstance(value, dict):
        raise AssertionError("list-cameras response included a non-object camera")

    name = value.get("name")
    if not isinstance(name, str):
        raise AssertionError("list-cameras response included a non-string camera name")

    return {"name": name}


def parse_camera_output(stdout: str) -> ListCamerasJson:
    try:
        document = json.loads(stdout)
    except json.JSONDecodeError as err:
        raise AssertionError(f"grpcurl did not emit valid JSON: {err}") from err
    if not isinstance(document, dict):
        raise AssertionError("grpcurl JSON output is not an object.")

    cameras = document.get("cameras", [])
    if not isinstance(cameras, list):
        raise AssertionError("list-cameras response did not include a cameras list")

    return {"cameras": [parse_camera(camera) for camera in cameras]}


def validate_camera_names(
    document: ListCamerasJson, expected_name_pattern: str | None
) -> tuple[bool, str]:
    cameras = document["cameras"]
    if not cameras:
        return False, "list-cameras response did not include any cameras"

    names: list[str] = []
    for camera in cameras:
        name = camera["name"]
        if not name.strip():
            return False, "list-cameras response included an empty camera name"
        names.append(name)

    if expected_name_pattern:
        pattern = re.compile(expected_name_pattern)
        if not any(pattern.search(name) for name in names):
            return False, "no camera name matched expected pattern"

    return True, "camera names matched expectations"


def fail_with_result(metadata: JsonObject, result: str, message: str) -> None:
    metadata["result"] = result
    pytest.fail(message)


def cleanup_and_record(metadata: JsonObject) -> None:
    cleanup_result = cleanup_compose(COMPOSE_FILE, cwd=REPO_ROOT)
    metadata["cleanup_exit_code"] = cleanup_result.returncode
    if cleanup_result.returncode != 0:
        write_command_transcript(
            TEST_RESULTS_DIR, "compose-cleanup.txt", cleanup_result
        )


def start_camera_service(metadata: JsonObject) -> None:
    up_result = run_command(*build_compose_command("up", "-d", "--build"))
    metadata["compose_up_exit_code"] = up_result.returncode
    if up_result.returncode != 0:
        write_command_transcript(TEST_RESULTS_DIR, "compose-up.txt", up_result)
        fail_with_result(
            metadata,
            "compose_start_failed",
            "Camera Compose startup command failed. See compose-up.txt.",
        )


def verify_camera_service_started(metadata: JsonObject) -> None:
    ready, startup_message = wait_for_startup()
    metadata["startup_ready"] = ready
    metadata["startup_result"] = startup_message
    if not ready:
        fail_with_result(metadata, "startup_readiness_failed", startup_message)


def call_grpc_list_cameras(
    metadata: JsonObject,
    discovery_attempts: int,
) -> CommandResult:
    result = run_grpcurl_list_cameras()
    metadata["camera_discovery_attempts"] = discovery_attempts
    metadata["camera_discovery_timeout_seconds"] = CAMERA_DISCOVERY_TIMEOUT_SECONDS
    metadata["list_cameras_exit_code"] = result.returncode
    write_text_artifact(TEST_RESULTS_DIR, "list-cameras.json", result.stdout)
    return result


def verify_list_cameras_output(
    metadata: JsonObject,
    result: CommandResult,
    expected_name_pattern: str | None,
) -> tuple[bool, str]:
    try:
        document = parse_camera_output(result.stdout)
    except AssertionError as err:
        fail_with_result(
            metadata,
            "unexpected_list_cameras_response",
            str(err),
        )

    valid, validation_reason = validate_camera_names(
        document,
        expected_name_pattern,
    )
    metadata["camera_count"] = len(document["cameras"])
    metadata["list_cameras_validation_result"] = validation_reason
    return valid, validation_reason


def verify_camera_discovery_via_grpc(metadata: JsonObject) -> None:
    discovery_deadline = time.monotonic() + CAMERA_DISCOVERY_TIMEOUT_SECONDS
    discovery_attempts = 0
    expected_name_pattern = os.environ.get(
        "CAMERA_BOARDFARM_EXPECTED_CAMERA_NAME_PATTERN"
    )
    last_result = "camera_discovery_timeout"
    last_message = "timed out waiting for camera discovery"

    while time.monotonic() < discovery_deadline:
        discovery_attempts += 1
        grpcurl_result = call_grpc_list_cameras(metadata, discovery_attempts)

        if grpcurl_result.returncode != 0:
            write_command_transcript(
                TEST_RESULTS_DIR, "list-cameras-command.txt", grpcurl_result
            )
            result = classify_grpcurl_failure(grpcurl_result)
            if result not in RETRYABLE_DISCOVERY_RESULTS:
                fail_with_result(
                    metadata,
                    result,
                    (
                        "grpcurl list-cameras call failed with "
                        f"{result}. See list-cameras-command.txt.\n"
                        f"{summarize_command_output(grpcurl_result)}"
                    ),
                )

            last_result = result
            last_message = (
                "grpcurl list-cameras call did not become ready before timeout: "
                f"{result}. See list-cameras-command.txt."
            )
            metadata["list_cameras_validation_result"] = result
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        valid, validation_reason = verify_list_cameras_output(
            metadata,
            grpcurl_result,
            expected_name_pattern,
        )
        if valid:
            return

        last_result = "unexpected_list_cameras_response"
        last_message = validation_reason
        time.sleep(POLL_INTERVAL_SECONDS)

    fail_with_result(metadata, last_result, last_message)


@pytest.fixture(scope="module")
def metadata() -> Iterator[JsonObject]:
    metadata = build_initial_metadata()
    try:
        yield metadata
    finally:
        metadata["finished_at"] = get_utc_now()
        write_diagnostics(metadata)
        cleanup_and_record(metadata)
        write_text_artifact(
            TEST_RESULTS_DIR,
            "metadata.json",
            json.dumps(metadata, indent=2, sort_keys=True),
        )


def test_camera_boardfarm_list_cameras_smoke(metadata: JsonObject) -> None:
    start_camera_service(metadata)
    verify_camera_service_started(metadata)
    verify_camera_discovery_via_grpc(metadata)
    metadata["result"] = "passed"
