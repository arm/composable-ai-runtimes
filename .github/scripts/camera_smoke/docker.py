from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import docker
from docker.errors import APIError, NotFound
from docker.models.containers import Container


@dataclass(frozen=True)
class ContainerState:
    status: str
    exit_code: str


def remove_container_by_name(client: docker.DockerClient, name: str) -> None:
    try:
        container = client.containers.get(name)
    except NotFound:
        return
    container.remove(force=True)


def cleanup_containers_by_prefix(client: docker.DockerClient, prefix: str) -> None:
    for container in client.containers.list(all=True):
        if not container.name.startswith(f"{prefix}-"):
            continue
        try:
            container.remove(force=True)
        except APIError as exc:
            print(f"Failed to remove Docker container {container.name}: {exc}")


def get_container_state(container: Container) -> ContainerState:
    try:
        container.reload()
    except NotFound:
        return ContainerState("missing", "missing")

    state = container.attrs.get("State") or {}
    return ContainerState(
        str(state.get("Status", "missing")),
        str(state.get("ExitCode", 0)),
    )


def get_container_logs(container: Container) -> str:
    try:
        logs = container.logs(stdout=True, stderr=True)
    except NotFound:
        return ""
    return logs.decode("utf-8", errors="replace")


def ensure_docker_image(
    client: docker.DockerClient,
    image_name: str,
    build_context: Path,
    *,
    build_env: str,
    description: str,
) -> None:
    if os.environ.get(build_env, "1") != "0":
        print(f"Building {description}.")
        client.images.build(
            path=str(build_context),
            tag=image_name,
            rm=True,
        )
        client.images.get(image_name)
        return

    print(f"Using existing {description}: {image_name}.")
    try:
        client.images.get(image_name)
    except NotFound as err:
        raise RuntimeError(
            f"{image_name} does not exist; build it first or set {build_env}=1."
        ) from err
