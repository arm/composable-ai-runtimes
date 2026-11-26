# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

"""Pytest startup smoke probes for the media service image."""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import docker
import pytest
from docker.errors import APIError, NotFound
from docker.models.containers import Container
from docker.models.volumes import Volume
from media_smoke.docker import (
    cleanup_containers_by_prefix,
    ensure_docker_image,
    get_container_logs,
    get_container_state,
    remove_container_by_name,
)
from media_smoke.github_actions import print_log_group

REPO_ROOT = Path(__file__).resolve().parents[2]
MEDIA_DIR = REPO_ROOT / "services" / "media"
MEDIA_IMAGE_NAME = "media-service:latest"
BUILD_IMAGE_ENV = "MEDIA_STARTUP_SMOKE_BUILD_IMAGE"
CONTAINER_PREFIX = (
    f"media-startup-smoke-{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.getpid()}"
)
RUNTIME_VOLUME = f"{CONTAINER_PREFIX}-runtime"
DIRECT_TIMEOUT_SECONDS = 8
TEST_RESULTS_DIR = REPO_ROOT / "test-results" / "media-startup-smoke"

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
def build_media_image(docker_client: docker.DockerClient) -> None:
    try:
        ensure_docker_image(
            docker_client,
            MEDIA_IMAGE_NAME,
            MEDIA_DIR,
            build_env=BUILD_IMAGE_ENV,
            description="media service image for startup smoke probes",
        )
    except RuntimeError as err:
        pytest.fail(str(err))


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

        print(f"Running media startup probe: {label}")
        container = docker_client.containers.run(
            MEDIA_IMAGE_NAME,
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
        print_log_group(f"{label} logs", log)

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
        entrypoint="/usr/local/bin/permissions-set-entrypoint.sh",
    )

    assert_usable_probe_log(result)
    assert log_contains(result, r"media-service"), (
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
        environment={"CAIRN_MEDIA_API_LISTEN_ADDR": "127.0.0.1:50051"},
        entrypoint="/usr/local/bin/api",
    )

    assert_usable_probe_log(result)
    assert log_contains(result, r"starting media API server"), (
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


@contextmanager
def aec_server(client: docker.DockerClient, enabled: bool) -> Iterator[Container]:
    environment = {"PIPEWIRE_DEBUG": "3"}
    if enabled:
        environment["CAIRN_ECHO_CANCEL"] = "1"
    container = client.containers.run(
        MEDIA_IMAGE_NAME,
        detach=True,
        name=f"{CONTAINER_PREFIX}-aec-{enabled}",
        environment=environment,
        cap_add=["SYS_NICE"],
        mounts=[docker.types.Mount(target="/run/pipewire", source=None, type="volume")],
    )
    try:
        # The entrypoint starts the media API after PipeWire has initialized.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            ready = container.exec_run(["grpc_health_probe", "-addr=127.0.0.1:50051"])
            if ready.exit_code == 0:
                break
            time.sleep(0.25)
        else:
            pytest.fail(f"Media API did not become ready: {container.logs()!r}")

        yield container
    finally:
        container.remove(force=True, v=True)


def pipewire_graph(container: Container) -> list[dict]:
    dump = container.exec_run(["pw-dump"], environment={"PIPEWIRE_DEBUG": "0"})
    assert dump.exit_code == 0, dump.output
    return json.loads(dump.output)


@pytest.mark.parametrize("enabled", [False, True], ids=["default", "enabled"])
def test_echo_cancellation_startup(
    docker_client: docker.DockerClient, enabled: bool
) -> None:
    with aec_server(docker_client, enabled) as container:
        graph = pipewire_graph(container)
        nodes = {
            props["node.name"]: props.get("media.class")
            for obj in graph
            if obj["type"] == "PipeWire:Interface:Node"
            for props in [obj["info"]["props"]]
            if props.get("node.name") in {"cairn.aec.sink", "cairn.aec.source"}
        }
        assert nodes == (
            {"cairn.aec.sink": "Audio/Sink", "cairn.aec.source": "Audio/Source"}
            if enabled
            else {}
        )

        # Confirm the image includes and loads the configured backend.
        assert (b"Using plugin AEC webrtc " in container.logs()) == enabled
