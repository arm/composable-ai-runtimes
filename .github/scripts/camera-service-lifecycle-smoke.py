#!/usr/bin/env python3
"""Quick lifecycle check for camera service supervision."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Iterator, NotRequired, TypedDict

import docker
import pytest
from docker.errors import NotFound
from docker.models.containers import Container

from camera_smoke.artifacts import write_text_artifact
from camera_smoke.docker import (
    cleanup_containers_by_prefix,
    get_container_logs,
    get_container_state,
    remove_container_by_name,
)
from camera_smoke.time import get_utc_now


REPO_ROOT = Path(__file__).resolve().parents[2]
CAMERA_DIR = REPO_ROOT / "services" / "camera"
CAMERA_IMAGE_NAME = "camera-service:latest"
BUILD_IMAGE_ENV = "CAMERA_LIFECYCLE_BUILD_IMAGE"
CONTAINER_PREFIX = (
    f"camera-lifecycle-{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.getpid()}"
)
RESULTS_DIR = REPO_ROOT / "test-results" / "camera-lifecycle"
SUPERVISED_PROCESSES = ["pipewire", "wireplumber", "api", "notifications"]
STARTUP_TIMEOUT_SECONDS = 30
EXIT_TIMEOUT_SECONDS = 10


class LifecycleMetadata(TypedDict):
    started_at: str
    supervised_processes: list[str]
    finished_at: NotRequired[str]


def print_probe_log(label: str, log: str) -> None:
    print(f"::group::{label} logs")
    try:
        print(log, end="")
    finally:
        print("::endgroup::")


def docker_exec(container: Container, command: list[str]) -> str:
    exec_result = container.exec_run(command)
    output = exec_result.output.decode("utf-8", errors="replace")
    if exec_result.exit_code != 0:
        raise RuntimeError(
            f"{command} failed with exit code {exec_result.exit_code}: {output}"
        )
    return output


def get_process_name(container: Container, pid: str) -> str | None:
    try:
        return docker_exec(container, ["cat", f"/proc/{pid}/comm"]).strip()
    except RuntimeError:
        return None


def get_pids_by_name(container: Container, target: str) -> list[str]:
    pids = []
    for entry in docker_exec(container, ["ls", "-1", "/proc"]).splitlines():
        if not entry.isdecimal():
            continue
        name = get_process_name(container, entry)
        if name == target:
            pids.append(entry)
    return pids


def wait_for_pid(container: Container, target: str) -> str:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        state = get_container_state(container)
        if state.status != "running":
            pytest.fail(f"Container is not running; status: {state.status}")

        pids = get_pids_by_name(container, target)
        if len(pids) == 1:
            return pids[0]
        if len(pids) > 1:
            pytest.fail(f"Expected one {target} process, found {pids}")

        time.sleep(1)

    pytest.fail(f"{target} did not start within {STARTUP_TIMEOUT_SECONDS} seconds")


def wait_for_container_exit(container: Container) -> None:
    deadline = time.monotonic() + EXIT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if get_container_state(container).status == "exited":
            return
        time.sleep(0.2)


def terminate_process(container: Container, pid: str) -> None:
    exec_result = container.exec_run(["/bin/sh", "-c", f"kill -TERM {pid}"])
    output = exec_result.output.decode("utf-8", errors="replace")
    assert exec_result.exit_code == 0, (
        f"Failed to terminate pid {pid}: exit_code={exec_result.exit_code} "
        f"output={output}"
    )


def should_build_camera_image() -> bool:
    return os.environ.get(BUILD_IMAGE_ENV, "1") != "0"


@pytest.fixture(scope="session", autouse=True)
def lifecycle_metadata() -> Iterator[LifecycleMetadata]:
    metadata: LifecycleMetadata = {
        "started_at": get_utc_now(),
        "supervised_processes": SUPERVISED_PROCESSES,
    }

    try:
        yield metadata
    finally:
        metadata["finished_at"] = get_utc_now()
        write_text_artifact(
            RESULTS_DIR,
            "metadata.json",
            json.dumps(metadata, indent=2, sort_keys=True),
        )


@pytest.fixture(scope="session")
def docker_client() -> Iterator[docker.DockerClient]:
    client = docker.from_env()
    try:
        client.ping()
        yield client
    finally:
        cleanup_containers_by_prefix(client, CONTAINER_PREFIX)
        client.close()


@pytest.fixture(scope="session", autouse=True)
def build_camera_image(
    lifecycle_metadata: LifecycleMetadata,
    docker_client: docker.DockerClient,
) -> None:
    if should_build_camera_image():
        print("Building camera service image for lifecycle check.")
        docker_client.images.build(
            path=str(CAMERA_DIR),
            tag=CAMERA_IMAGE_NAME,
            rm=True,
        )
        docker_client.images.get(CAMERA_IMAGE_NAME)
        return

    print(
        f"Using existing camera service image for lifecycle check: {CAMERA_IMAGE_NAME}."
    )
    try:
        docker_client.images.get(CAMERA_IMAGE_NAME)
    except NotFound:
        pytest.fail(
            f"{CAMERA_IMAGE_NAME} does not exist; build it first or set "
            f"{BUILD_IMAGE_ENV}=1."
        )


@pytest.fixture
def lifecycle_container(
    target_process: str,
    docker_client: docker.DockerClient,
) -> Iterator[Container]:
    name = f"{CONTAINER_PREFIX}-{target_process}"
    remove_container_by_name(docker_client, name)

    container = None
    try:
        container = docker_client.containers.run(
            CAMERA_IMAGE_NAME,
            detach=True,
            name=name,
            cap_add=["SYS_NICE"],
        )
        yield container
    finally:
        if container is not None:
            logs = get_container_logs(container)
            write_text_artifact(RESULTS_DIR, f"{name}.log", logs)
            print_probe_log(f"camera lifecycle {name}", logs)
        remove_container_by_name(docker_client, name)


@pytest.mark.parametrize("target_process", SUPERVISED_PROCESSES)
def test_container_exits_non_zero_when_supervised_process_dies(
    target_process: str,
    lifecycle_container: Container,
) -> None:
    target_pid = wait_for_pid(lifecycle_container, target_process)
    terminate_process(lifecycle_container, target_pid)

    wait_for_container_exit(lifecycle_container)
    final_state = get_container_state(lifecycle_container)

    assert final_state.status == "exited", (
        f"Container stayed {final_state.status} after {target_process} was killed"
    )
    assert final_state.exit_code != "0", (
        f"Entrypoint exited 0 after {target_process} was killed"
    )
