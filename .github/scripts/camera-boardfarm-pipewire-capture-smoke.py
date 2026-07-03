#!/usr/bin/env python3
"""Pytest direct PipeWire capture smoke probe for the board-farm deployment."""

from __future__ import annotations

import json
import os
import platform
import socket
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, TypedDict

import docker
import pytest
from docker.errors import APIError, BuildError, DockerException
from docker.models.containers import Container

from camera_smoke.artifacts import (
    write_command_transcript,
    write_text_artifact,
)
from camera_smoke.camera_service import CAMERA_STARTUP_FAILURE_PATTERN
from camera_smoke.commands import CommandResult, run_command
from camera_smoke.compose import (
    build_compose_command,
    cleanup_compose,
    get_compose_logs,
    has_compose_service_exited,
    is_compose_service_running,
    write_compose_diagnostics,
)
from camera_smoke.docker import remove_container_by_name
from camera_smoke.network import can_connect_to_tcp
from camera_smoke.time import get_utc_now


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "services" / "camera" / "compose.yaml"
CLIENT_CONTEXT = REPO_ROOT / ".github" / "scripts" / "camera_smoke"
CLIENT_DOCKERFILE = CLIENT_CONTEXT / "pipewire_capture.Dockerfile"
TEST_RESULTS_DIR = REPO_ROOT / "test-results" / "camera-boardfarm-pipewire-capture-smoke"
SERVICE_NAME = "camera-service"
GRPC_HOST = "127.0.0.1"
GRPC_PORT = 50051
STARTUP_TIMEOUT_SECONDS = 60
POLL_INTERVAL_SECONDS = 2
CLIENT_IMAGE_TAG = "camera-boardfarm-pipewire-capture-client:latest"
CLIENT_CONTAINER_NAME = "camera-boardfarm-pipewire-capture-client"
COMMAND_OUTPUT_SUMMARY_LIMIT = 1000
PIPEWIRE_TARGET_OBJECT_ENV = "CAMERA_BOARDFARM_PIPEWIRE_TARGET_OBJECT"
PIPEWIRE_CAMERA_NAME_ENV = "CAMERA_BOARDFARM_PIPEWIRE_CAMERA_NAME"
DEFAULT_PIPEWIRE_CAMERA_NAME = "fixed-boardfarm-camera"
JsonObject = dict[str, object]


@dataclass(frozen=True)
class CameraTarget:
    pipewire_target_object: str
    name: str


class CaptureJson(TypedDict):
    pipewire_target_object: str
    camera_name: str
    frame_bytes: int
    width: int
    height: int
    pixel_format: str
    caps: str
    stride: int | None
    stride_error: str | None


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


def read_os_release() -> str | None:
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if key == "PRETTY_NAME" and separator:
                return value.strip().strip('"')
    except OSError:
        return None
    return None


def build_initial_metadata() -> JsonObject:
    return {
        "started_at": get_utc_now(),
        "compose_file": str(COMPOSE_FILE.relative_to(REPO_ROOT)),
        "compose_project_name": os.environ.get("COMPOSE_PROJECT_NAME"),
        "configured_pipewire_target_object": os.environ.get(PIPEWIRE_TARGET_OBJECT_ENV),
        "configured_pipewire_camera_name": os.environ.get(PIPEWIRE_CAMERA_NAME_ENV),
        "hostname": socket.gethostname(),
        "os_release": read_os_release(),
        "kernel_release": platform.release(),
        "capture_client_image": CLIENT_IMAGE_TAG,
        "result": "started",
    }


def fail_with_result(metadata: JsonObject, result: str, message: str) -> None:
    metadata["result"] = result
    pytest.fail(message)


def cleanup_compose_and_record_result(metadata: JsonObject) -> None:
    cleanup_result = cleanup_compose(COMPOSE_FILE, cwd=REPO_ROOT)
    metadata["cleanup_exit_code"] = cleanup_result.returncode
    if cleanup_result.returncode != 0:
        write_command_transcript(
            TEST_RESULTS_DIR, "compose-cleanup.txt", cleanup_result
        )


def start_camera_service(metadata: JsonObject) -> None:
    up_result = run_command(
        *build_compose_command(COMPOSE_FILE, "up", "-d", "--build"),
        cwd=REPO_ROOT,
    )
    metadata["compose_up_exit_code"] = up_result.returncode
    if up_result.returncode != 0:
        write_command_transcript(TEST_RESULTS_DIR, "compose-up.txt", up_result)
        fail_with_result(
            metadata,
            "service_runtime_socket_setup_failed",
            "Camera Compose startup command failed. See compose-up.txt.",
        )


def verify_camera_service_started(metadata: JsonObject) -> None:
    ready, startup_message = wait_for_startup()
    metadata["startup_ready"] = ready
    metadata["startup_result"] = startup_message
    if not ready:
        fail_with_result(
            metadata, "service_runtime_socket_setup_failed", startup_message
        )


def summarize_command_output(result: CommandResult) -> str:
    output = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}".strip()
    if len(output) <= COMMAND_OUTPUT_SUMMARY_LIMIT:
        return output
    return f"{output[:COMMAND_OUTPUT_SUMMARY_LIMIT]}...<truncated>"


def decode_docker_output(output: bytes | str) -> str:
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return output


def build_log_text(build_log: object) -> str:
    if isinstance(build_log, str) or not isinstance(build_log, Iterable):
        return str(build_log)

    lines: list[str] = []
    for entry in build_log:
        if isinstance(entry, dict):
            for key in ("stream", "status", "error"):
                value = entry.get(key)
                if value:
                    lines.append(str(value).rstrip())
        else:
            lines.append(str(entry).rstrip())
    return "\n".join(line for line in lines if line)


def get_configured_camera_target(metadata: JsonObject) -> CameraTarget:
    target_object = os.environ.get(PIPEWIRE_TARGET_OBJECT_ENV, "").strip()
    if not target_object:
        fail_with_result(
            metadata,
            "pipewire_capture_failed",
            (
                f"{PIPEWIRE_TARGET_OBJECT_ENV} must be set to the fixed PipeWire "
                "camera target object"
            ),
        )

    camera_name = (
        os.environ.get(PIPEWIRE_CAMERA_NAME_ENV, "").strip()
        or DEFAULT_PIPEWIRE_CAMERA_NAME
    )
    metadata["selected_pipewire_target_object"] = target_object
    metadata["selected_camera_name"] = camera_name
    return CameraTarget(pipewire_target_object=target_object, name=camera_name)


def build_capture_client_image(
    metadata: JsonObject,
    docker_client: docker.DockerClient,
) -> None:
    build_args = [
        "docker-sdk",
        "images.build",
        "--tag",
        CLIENT_IMAGE_TAG,
        "--file",
        str(CLIENT_DOCKERFILE),
        str(CLIENT_CONTEXT),
    ]
    try:
        _image, logs = docker_client.images.build(
            path=str(CLIENT_CONTEXT),
            dockerfile=CLIENT_DOCKERFILE.name,
            tag=CLIENT_IMAGE_TAG,
            rm=True,
            forcerm=True,
        )
        result = CommandResult(
            args=build_args,
            returncode=0,
            stdout=build_log_text(logs),
            stderr="",
        )
    except BuildError as err:
        result = CommandResult(
            args=build_args,
            returncode=1,
            stdout=build_log_text(err.build_log),
            stderr=str(err),
        )
    except DockerException as err:
        result = CommandResult(
            args=build_args,
            returncode=1,
            stdout="",
            stderr=str(err),
        )

    metadata["capture_client_build_exit_code"] = result.returncode
    write_command_transcript(TEST_RESULTS_DIR, "pipewire-capture-build.txt", result)
    if result.returncode != 0:
        fail_with_result(
            metadata,
            "pipewire_capture_failed",
            (
                "PipeWire capture client image build failed. See "
                "pipewire-capture-build.txt.\n"
                f"{summarize_command_output(result)}"
            ),
        )


def compose_volume_name() -> str:
    project_name = os.environ.get("COMPOSE_PROJECT_NAME")
    if project_name:
        return f"{project_name}_pipewire-runtime"
    return "camera_pipewire-runtime"


def container_output(container: Container, *, stdout: bool, stderr: bool) -> str:
    return decode_docker_output(container.logs(stdout=stdout, stderr=stderr))


def run_capture_client(
    docker_client: docker.DockerClient,
    camera: CameraTarget,
) -> CommandResult:
    command = [
        "--pipewire-target-object",
        camera.pipewire_target_object,
        "--camera-name",
        camera.name,
    ]
    run_args = [
        "docker-sdk",
        "containers.run",
        "--network",
        "host",
        "--env",
        "XDG_RUNTIME_DIR=/run/pipewire",
        "--volume",
        f"{compose_volume_name()}:/run/pipewire",
        CLIENT_IMAGE_TAG,
        *command,
    ]

    remove_container_by_name(docker_client, CLIENT_CONTAINER_NAME)
    container: Container | None = None
    try:
        container = docker_client.containers.run(
            CLIENT_IMAGE_TAG,
            command=command,
            detach=True,
            name=CLIENT_CONTAINER_NAME,
            network_mode="host",
            environment={"XDG_RUNTIME_DIR": "/run/pipewire"},
            mounts=[
                docker.types.Mount(
                    target="/run/pipewire",
                    source=compose_volume_name(),
                    type="volume",
                )
            ],
        )
        wait_result = container.wait()
        return CommandResult(
            args=run_args,
            returncode=int(wait_result.get("StatusCode", 1)),
            stdout=container_output(container, stdout=True, stderr=False),
            stderr=container_output(container, stdout=False, stderr=True),
        )
    except (APIError, DockerException) as err:
        return CommandResult(
            args=run_args,
            returncode=1,
            stdout="",
            stderr=str(err),
        )
    finally:
        if container is not None:
            remove_container_by_name(docker_client, CLIENT_CONTAINER_NAME)


def parse_capture_output(stdout: str) -> CaptureJson:
    try:
        document = json.loads(stdout)
    except json.JSONDecodeError as err:
        raise AssertionError(f"PipeWire capture probe did not emit valid JSON: {err}") from err
    assert isinstance(document, dict), (
        "PipeWire capture probe JSON output is not an object"
    )

    pipewire_target_object = document.get("pipewire_target_object")
    camera_name = document.get("camera_name")
    frame_bytes = document.get("frame_bytes")
    width = document.get("width")
    height = document.get("height")
    pixel_format = document.get("pixel_format")
    caps = document.get("caps")
    stride = document.get("stride")
    stride_error = document.get("stride_error")

    assert isinstance(pipewire_target_object, str), (
        "PipeWire capture output included a non-string pipewire_target_object"
    )
    assert isinstance(camera_name, str), (
        "PipeWire capture output included a non-string camera_name"
    )
    assert isinstance(frame_bytes, int), (
        "PipeWire capture output included a non-integer frame_bytes"
    )
    assert isinstance(width, int), (
        "PipeWire capture output included a non-integer width"
    )
    assert isinstance(height, int), (
        "PipeWire capture output included a non-integer height"
    )
    assert isinstance(pixel_format, str), (
        "PipeWire capture output included a non-string pixel_format"
    )
    assert isinstance(caps, str), (
        "PipeWire capture output included non-string caps"
    )
    assert stride is None or isinstance(stride, int), (
        "PipeWire capture output included an invalid stride"
    )
    assert stride_error is None or isinstance(stride_error, str), (
        "PipeWire capture output included an invalid stride_error"
    )

    return {
        "pipewire_target_object": pipewire_target_object,
        "camera_name": camera_name,
        "frame_bytes": frame_bytes,
        "width": width,
        "height": height,
        "pixel_format": pixel_format,
        "caps": caps,
        "stride": stride,
        "stride_error": stride_error,
    }


def validate_capture_output(document: CaptureJson, camera: CameraTarget) -> None:
    assert document["pipewire_target_object"] == camera.pipewire_target_object, (
        "PipeWire capture output target object did not match selection"
    )
    assert document["camera_name"] == camera.name, (
        "PipeWire capture output camera name did not match selection"
    )
    assert document["frame_bytes"] > 0, "PipeWire capture returned an empty frame"
    assert document["width"] > 0, "PipeWire capture returned an invalid frame width"
    assert document["height"] > 0, "PipeWire capture returned an invalid frame height"
    assert document["pixel_format"].strip(), (
        "PipeWire capture returned an empty pixel format"
    )
    assert document["caps"].strip(), "PipeWire capture returned empty caps"


def record_capture_metadata(metadata: JsonObject, document: CaptureJson) -> None:
    metadata["frame_width"] = document["width"]
    metadata["frame_height"] = document["height"]
    metadata["frame_stride"] = document["stride"]
    metadata["frame_stride_error"] = document["stride_error"]
    metadata["frame_pixel_format"] = document["pixel_format"]
    metadata["frame_caps"] = document["caps"]
    metadata["frame_byte_count"] = document["frame_bytes"]


def verify_direct_pipewire_capture(
    metadata: JsonObject,
    docker_client: docker.DockerClient,
    camera: CameraTarget,
) -> None:
    build_capture_client_image(metadata, docker_client)
    result = run_capture_client(docker_client, camera)
    metadata["pipewire_capture_exit_code"] = result.returncode
    write_command_transcript(
        TEST_RESULTS_DIR, "direct-pipewire-capture-command.txt", result
    )
    write_text_artifact(TEST_RESULTS_DIR, "direct-pipewire-capture.json", result.stdout)

    if result.returncode != 0:
        fail_with_result(
            metadata,
            "pipewire_capture_failed",
            (
                "PipeWire capture probe failed. See "
                "direct-pipewire-capture-command.txt.\n"
                f"{summarize_command_output(result)}"
            ),
        )

    document = parse_capture_output(result.stdout)
    validate_capture_output(document, camera)

    record_capture_metadata(metadata, document)


@pytest.fixture(scope="module")
def pipewire_capture_metadata() -> Iterator[JsonObject]:
    metadata = build_initial_metadata()
    try:
        yield metadata
    finally:
        metadata["finished_at"] = get_utc_now()
        write_compose_diagnostics(
            TEST_RESULTS_DIR, COMPOSE_FILE, metadata, cwd=REPO_ROOT
        )
        cleanup_compose_and_record_result(metadata)
        write_text_artifact(
            TEST_RESULTS_DIR,
            "metadata.json",
            json.dumps(metadata, indent=2, sort_keys=True),
        )


@pytest.fixture(scope="module")
def docker_client() -> Iterator[docker.DockerClient]:
    client = docker.from_env()
    try:
        client.ping()
        yield client
    finally:
        remove_container_by_name(client, CLIENT_CONTAINER_NAME)
        client.close()


def test_camera_boardfarm_pipewire_capture_smoke(
    pipewire_capture_metadata: JsonObject,
    docker_client: docker.DockerClient,
) -> None:
    start_camera_service(pipewire_capture_metadata)
    verify_camera_service_started(pipewire_capture_metadata)
    camera = get_configured_camera_target(pipewire_capture_metadata)
    verify_direct_pipewire_capture(pipewire_capture_metadata, docker_client, camera)
    pipewire_capture_metadata["result"] = "passed"
