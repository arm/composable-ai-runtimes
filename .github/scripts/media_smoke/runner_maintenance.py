# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from collections.abc import Sequence
from typing import Literal

MANAGED_PROJECT_PATTERN = re.compile(r"^camera-boardfarm-(?:[a-z0-9]+-)*[0-9]+$")
COMPOSE_PROJECT_LABEL = "com.docker.compose.project"
CAPTURE_CLIENT_CONTAINER = "camera-boardfarm-pipewire-capture-client"
PRUNE_BELOW_PERCENT_FREE = 20.0
FAIL_BELOW_PERCENT_FREE = 10.0
BUILD_STORAGE_RETENTION_HOURS = 24
ContainerEngine = Literal["docker", "podman"]
ContainerResourceType = Literal["container", "volume", "network"]
ENGINES: tuple[ContainerEngine, ...] = ("docker", "podman")
RESOURCE_TYPES: tuple[ContainerResourceType, ...] = (
    "container",
    "volume",
    "network",
)
RESOURCE_IDENTIFIER_FIELDS: dict[ContainerResourceType, str] = {
    "container": "ID",
    "volume": "Name",
    "network": "ID",
}
PODMAN_IDENTIFIER_FIELDS: dict[ContainerResourceType, tuple[str, ...]] = {
    "container": ("Id", "ID", "id"),
    "volume": ("Name", "name"),
    "network": ("id", "ID"),
}


def engine_command(engine: ContainerEngine, *args: str) -> tuple[str, ...]:
    if engine == "docker":
        return (engine, *args)
    if engine == "podman":
        return ("sudo", "--non-interactive", engine, *args)
    raise ValueError(f"unsupported container engine: {engine}")


def run_command(
    args: Sequence[str], *, check: bool = True, capture_output: bool = False
) -> subprocess.CompletedProcess[str]:
    print(f"$ {shlex.join(args)}", flush=True)
    return subprocess.run(
        args,
        check=check,
        capture_output=capture_output,
        text=True,
    )


def is_managed_project(project: str) -> bool:
    return MANAGED_PROJECT_PATTERN.fullmatch(project) is not None


def docker_resource_list_format(resource_type: ContainerResourceType) -> str:
    identifier_field = RESOURCE_IDENTIFIER_FIELDS[resource_type]
    label_field = f'{{{{.Label "{COMPOSE_PROJECT_LABEL}"}}}}'
    return f"{{{{.{identifier_field}}}}}\t{label_field}"


def podman_record_value(record: dict[object, object], fields: Sequence[str]) -> object:
    for field in fields:
        if field in record:
            return record[field]
    return None


def parse_podman_resource_ids(
    output: str, resource_type: ContainerResourceType
) -> list[str]:
    records: object = json.loads(output)
    if not isinstance(records, list):
        raise TypeError(f"unexpected Podman {resource_type} list JSON")

    resource_ids: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            raise TypeError(f"unexpected Podman {resource_type} record")

        resource_id = podman_record_value(
            record, PODMAN_IDENTIFIER_FIELDS[resource_type]
        )
        labels = podman_record_value(record, ("Labels", "labels"))
        if not isinstance(resource_id, str) or not isinstance(labels, dict):
            raise TypeError(f"unexpected Podman {resource_type} record fields")

        project = labels.get(COMPOSE_PROJECT_LABEL)
        if not isinstance(project, str):
            raise TypeError(
                f"Podman {resource_type} record is missing its filtered Compose label"
            )
        if is_managed_project(project):
            resource_ids.append(resource_id)
    return resource_ids


def list_managed_resource_ids(
    engine: ContainerEngine, resource_type: ContainerResourceType
) -> list[str]:
    args = [resource_type, "ls"]
    if resource_type == "container":
        args.append("--all")
    output_format = (
        docker_resource_list_format(resource_type) if engine == "docker" else "json"
    )
    args.extend(
        ("--filter", f"label={COMPOSE_PROJECT_LABEL}", "--format", output_format)
    )
    result = run_command(engine_command(engine, *args), capture_output=True)

    if engine == "podman":
        return parse_podman_resource_ids(result.stdout, resource_type)

    resource_ids: list[str] = []
    for line in result.stdout.splitlines():
        resource_id, separator, project = line.partition("\t")
        resource_id = resource_id.strip()
        project = project.strip() if separator else ""
        if resource_id and project and is_managed_project(project):
            resource_ids.append(resource_id)
    return resource_ids


def remove_resources(
    engine: ContainerEngine,
    resource_type: ContainerResourceType,
    resource_ids: Sequence[str],
) -> None:
    if not resource_ids:
        return
    args = [resource_type, "rm"]
    if resource_type == "container":
        args.append("--force")
    run_command(engine_command(engine, *args, *resource_ids))


def remove_stale_compose_projects() -> None:
    for engine in ENGINES:
        for resource_type in RESOURCE_TYPES:
            remove_resources(
                engine,
                resource_type,
                list_managed_resource_ids(engine, resource_type),
            )


def remove_stale_capture_client() -> None:
    result = run_command(
        engine_command(
            "docker", "container", "rm", "--force", CAPTURE_CLIENT_CONTAINER
        ),
        check=False,
        capture_output=True,
    )
    if result.returncode != 0 and "No such container" not in result.stderr:
        detail = (
            result.stderr.strip() or f"docker exited with status {result.returncode}"
        )
        raise RuntimeError(f"failed to remove stale capture client: {detail}")


def percent_free(path: str = "/") -> float:
    usage = shutil.disk_usage(path)
    return usage.free / usage.total * 100


def prune_unused_build_storage() -> None:
    retention = f"until={BUILD_STORAGE_RETENTION_HOURS}h"
    run_command(
        engine_command(
            "docker", "image", "prune", "--all", "--force", "--filter", retention
        )
    )
    run_command(
        engine_command(
            "docker", "builder", "prune", "--all", "--force", "--filter", retention
        )
    )
    run_command(
        engine_command(
            "podman",
            "image",
            "prune",
            "--all",
            "--force",
            "--build-cache",
            "--filter",
            retention,
        )
    )


def validate_current_project() -> None:
    project = os.environ.get("COMPOSE_PROJECT_NAME", "").strip()
    if not is_managed_project(project):
        raise RuntimeError(
            "COMPOSE_PROJECT_NAME must identify the current camera board-farm run"
        )


def maintain_runner() -> None:
    validate_current_project()
    remove_stale_compose_projects()
    remove_stale_capture_client()

    free_percent = percent_free()
    print(f"Root filesystem free space: {free_percent:.1f}%")
    if free_percent < PRUNE_BELOW_PERCENT_FREE:
        prune_unused_build_storage()
        free_percent = percent_free()
        print(f"Root filesystem free space after pruning: {free_percent:.1f}%")

    emergency_prunes = (
        engine_command("docker", "builder", "prune", "--all", "--force"),
        engine_command("podman", "image", "prune", "--all", "--force", "--build-cache"),
        engine_command("docker", "image", "prune", "--all", "--force"),
    )
    for command in emergency_prunes:
        if free_percent >= FAIL_BELOW_PERCENT_FREE:
            break
        print(
            "Disk space remains below the safety floor; pruning unused build storage without age retention"
        )
        run_command(command)
        free_percent = percent_free()
        print(
            f"Root filesystem free space after emergency pruning: {free_percent:.1f}%"
        )

    if free_percent < FAIL_BELOW_PERCENT_FREE:
        raise RuntimeError(
            "root filesystem remains below the "
            f"{FAIL_BELOW_PERCENT_FREE:.0f}% free-space safety floor"
        )


def main() -> None:
    maintain_runner()


if __name__ == "__main__":
    main()
