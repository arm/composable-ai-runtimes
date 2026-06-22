#!/usr/bin/env python3
"""Pytest startup smoke probes for the camera service image."""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import docker
import pytest
from docker.errors import APIError, NotFound
from docker.models.volumes import Volume

from camera_smoke.docker import (
    cleanup_containers_by_prefix,
    get_container_logs,
    get_container_state,
    remove_container_by_name,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CAMERA_DIR = REPO_ROOT / "services" / "camera"
CAMERA_IMAGE_NAME = "camera-service:latest"
BUILD_IMAGE_ENV = "CAMERA_STARTUP_SMOKE_BUILD_IMAGE"
CONTAINER_PREFIX = (
    f"camera-startup-smoke-{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.getpid()}"
)
RUNTIME_VOLUME = f"{CONTAINER_PREFIX}-runtime"
DIRECT_TIMEOUT_SECONDS = 8
TEST_RESULTS_DIR = REPO_ROOT / "test-results" / "camera-startup-smoke"

UNEXPECTED_STARTUP_ERROR_PATTERN = re.compile(
    r"panic|panicked|thread .* panicked|segmentation fault|illegal instruction|"
    r"No such file or directory \(os error 2\).*api|"
    r"No such file or directory \(os error 2\).*notifications",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ProbeResult:
    label: str
    log: str
    status: str
    exit_code: str


def remove_volume(
    client: docker.DockerClient, name: str, *, ignore_errors: bool = False
) -> None:
    try:
        volume = client.volumes.get(name)
    except NotFound:
        return
    try:
        volume.remove(force=True)
    except APIError as exc:
        if not ignore_errors:
            raise
        print(f"Failed to remove Docker volume {name}: {exc}")


def cleanup_all(client: docker.DockerClient) -> None:
    cleanup_containers_by_prefix(client, CONTAINER_PREFIX)

    remove_volume(client, RUNTIME_VOLUME, ignore_errors=True)


def print_probe_log(label: str, log: str) -> None:
    print(f"::group::{label} logs")
    try:
        print(log, end="")
    finally:
        print("::endgroup::")


def save_probe_log(label: str, log: str) -> None:
    TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (TEST_RESULTS_DIR / f"{label}.log").write_text(log, encoding="utf-8")


def log_contains(result: ProbeResult, pattern: str | re.Pattern[str]) -> bool:
    return re.search(pattern, result.log) is not None


def assert_usable_probe_log(result: ProbeResult) -> None:
    assert result.log, (
        f"Probe {result.label} produced no startup or dependency-failure logs."
    )
    assert not UNEXPECTED_STARTUP_ERROR_PATTERN.search(result.log), (
        f"Probe {result.label} logged an unexpected startup error."
    )


def assert_running_at_end(result: ProbeResult) -> None:
    if result.status == "exited":
        pytest.fail(
            f"Probe {result.label} exited with code {result.exit_code}; expected it to "
            "stay running during the smoke window."
        )

    assert result.status == "running", (
        f"Probe {result.label} finished with unexpected container status: "
        f"{result.status}."
    )


def should_build_camera_image() -> bool:
    return os.environ.get(BUILD_IMAGE_ENV, "1") != "0"


@pytest.fixture(scope="session")
def docker_client() -> Iterator[docker.DockerClient]:
    client = docker.from_env()
    try:
        client.ping()
        yield client
    finally:
        cleanup_all(client)
        client.close()


@pytest.fixture(scope="session", autouse=True)
def build_camera_image(docker_client: docker.DockerClient) -> None:
    if should_build_camera_image():
        print("Building camera service image for startup smoke probes.")
        docker_client.images.build(
            path=str(CAMERA_DIR),
            tag=CAMERA_IMAGE_NAME,
            rm=True,
        )
        docker_client.images.get(CAMERA_IMAGE_NAME)
        return

    print(f"Using existing camera service image for startup smoke probes: {CAMERA_IMAGE_NAME}.")
    try:
        docker_client.images.get(CAMERA_IMAGE_NAME)
    except NotFound:
        pytest.fail(
            f"{CAMERA_IMAGE_NAME} does not exist; build it first or set "
            f"{BUILD_IMAGE_ENV}=1."
        )


@pytest.fixture
def runtime_volume(docker_client: docker.DockerClient) -> Iterator[Volume]:
    remove_volume(docker_client, RUNTIME_VOLUME)
    volume = docker_client.volumes.create(name=RUNTIME_VOLUME)
    try:
        yield volume
    finally:
        remove_volume(docker_client, RUNTIME_VOLUME)


@pytest.fixture
def run_container_probe(docker_client: docker.DockerClient):
    def _run_container_probe(
        label: str, timeout_seconds: int, **run_kwargs: object
    ) -> ProbeResult:
        name = f"{CONTAINER_PREFIX}-{label}"

        remove_container_by_name(docker_client, name)

        print(f"Running camera startup probe: {label}")
        container = docker_client.containers.run(
            CAMERA_IMAGE_NAME,
            detach=True,
            name=name,
            **run_kwargs,
        )

        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            status = get_container_state(container).status
            if status in {"missing", "exited"}:
                break

            time.sleep(1)

        log = get_container_logs(container)
        save_probe_log(label, log)
        print_probe_log(label, log)

        state = get_container_state(container)
        remove_container_by_name(docker_client, name)
        assert state.status != "missing", f"Probe {label} container disappeared."

        return ProbeResult(
            label,
            log,
            state.status,
            state.exit_code,
        )

    return _run_container_probe


def test_missing_runtime_failure(run_container_probe) -> None:
    label = "missing-runtime"
    result = run_container_probe(
        label,
        DIRECT_TIMEOUT_SECONDS,
        environment={"XDG_RUNTIME_DIR": f"/tmp/{CONTAINER_PREFIX}-missing-runtime"},
        entrypoint="/usr/local/bin/entrypoint.sh",
    )

    assert_usable_probe_log(result)
    assert log_contains(result, r"missing runtime directory"), (
        f"Probe {label} did not log the expected missing runtime directory failure."
    )

    assert result.status == "exited" and result.exit_code != "0", (
        f"Probe {label} did not fail fast on the missing runtime directory."
    )


def test_permissions_entrypoint_repairs_runtime_and_drops_privileges(
    runtime_volume: Volume, run_container_probe
) -> None:
    label = "permissions-entrypoint"

    result = run_container_probe(
        label,
        DIRECT_TIMEOUT_SECONDS,
        command=[
            "sh",
            "-c",
            'id -un && test -w "$XDG_RUNTIME_DIR" && echo runtime-writable',
        ],
        user="root",
        mounts=[
            docker.types.Mount(
                target="/run/pipewire",
                source=runtime_volume.name,
                type="volume",
            )
        ],
        environment={"XDG_RUNTIME_DIR": "/run/pipewire"},
        entrypoint="/usr/local/bin/permissions-set-entrypint.sh",
    )

    assert_usable_probe_log(result)
    assert log_contains(result, r"camera-service"), (
        f"Probe {label} did not log the dropped user."
    )
    assert log_contains(result, r"runtime-writable"), (
        f"Probe {label} did not log the repaired runtime directory."
    )
    assert result.status == "exited" and result.exit_code == "0", (
        f"Probe {label} did not exit successfully after repairing the runtime "
        f"directory; status={result.status}, exit_code={result.exit_code}."
    )


def test_api_startup(run_container_probe) -> None:
    label = "api-startup"
    result = run_container_probe(
        label,
        DIRECT_TIMEOUT_SECONDS,
        environment={"CAMERA_API_LISTEN_ADDR": "127.0.0.1:50051"},
        entrypoint="/usr/local/bin/api",
    )

    assert_usable_probe_log(result)
    assert log_contains(result, r"starting camera API server"), (
        f"Probe {label} did not log API startup."
    )
    assert_running_at_end(result)


def test_notifications_redis_unavailable(run_container_probe) -> None:
    label = "notifications-redis-unavailable"
    result = run_container_probe(
        label,
        DIRECT_TIMEOUT_SECONDS,
        environment={"PWC_REDIS_HOST": "127.0.0.1", "PWC_REDIS_PORT": "6379"},
        entrypoint="/usr/local/bin/notifications",
    )

    assert_usable_probe_log(result)
    assert log_contains(result, r"connecting notifications Redis client"), (
        f"Probe {label} did not log notifications startup."
    )
    assert log_contains(
        result, r"failed to connect notifications Redis client; retrying"
    ), f"Probe {label} did not log the expected Redis-unavailable retry."
    assert_running_at_end(result)
