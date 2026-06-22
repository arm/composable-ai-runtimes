from __future__ import annotations

from dataclasses import dataclass

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
