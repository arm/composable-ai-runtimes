# SPDX-FileCopyrightText: Copyright 2026 Arm Limited and/or its affiliates <open-source-office@arm.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from camera_smoke.artifacts import write_command_transcript, write_text_artifact
from camera_smoke.commands import CommandResult, run_command


@dataclass(frozen=True)
class ComposeRuntime:
    container_engine: str
    project_name: str | None
    use_sudo: bool
    build_image: bool


DEFAULT_COMPOSE_RUNTIME = ComposeRuntime(
    container_engine="docker",
    project_name=None,
    use_sudo=False,
    build_image=True,
)


def build_compose_command(
    compose_file: Path,
    *args: str,
    runtime: ComposeRuntime = DEFAULT_COMPOSE_RUNTIME,
) -> list[str]:
    command = [runtime.container_engine, "compose"]
    if runtime.project_name:
        command.extend(["--project-name", runtime.project_name])
    if runtime.use_sudo:
        command = ["sudo", "--non-interactive", *command]
    return [*command, "-f", str(compose_file), *args]


def get_compose_logs(
    compose_file: Path,
    *,
    cwd: Path,
    runtime: ComposeRuntime = DEFAULT_COMPOSE_RUNTIME,
) -> str:
    result = run_command(
        *build_compose_command(
            compose_file,
            "logs",
            "--no-color",
            runtime=runtime,
        ),
        cwd=cwd,
    )
    return result.stdout + result.stderr


def get_compose_ps(
    compose_file: Path,
    *,
    cwd: Path,
    runtime: ComposeRuntime = DEFAULT_COMPOSE_RUNTIME,
) -> CommandResult:
    return run_command(
        *build_compose_command(
            compose_file,
            "ps",
            "--all",
            runtime=runtime,
        ),
        cwd=cwd,
    )


def write_compose_diagnostics(
    results_dir: Path,
    compose_file: Path,
    metadata: Mapping[str, object],
    *,
    cwd: Path,
    runtime: ComposeRuntime = DEFAULT_COMPOSE_RUNTIME,
) -> None:
    write_text_artifact(
        results_dir,
        "compose.log",
        get_compose_logs(
            compose_file,
            cwd=cwd,
            runtime=runtime,
        ),
    )
    write_command_transcript(
        results_dir,
        "compose-ps.txt",
        get_compose_ps(
            compose_file,
            cwd=cwd,
            runtime=runtime,
        ),
    )
    write_text_artifact(
        results_dir, "metadata.json", json.dumps(metadata, indent=2, sort_keys=True)
    )


def is_compose_service_in_status(
    compose_file: Path,
    service_name: str,
    status: str,
    *,
    cwd: Path,
    runtime: ComposeRuntime = DEFAULT_COMPOSE_RUNTIME,
) -> bool:
    result = run_command(
        *build_compose_command(
            compose_file,
            "ps",
            "--status",
            status,
            "--services",
            runtime=runtime,
        ),
        cwd=cwd,
    )
    if result.returncode != 0:
        return False

    services = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return service_name in services


def is_compose_service_running(
    compose_file: Path,
    service_name: str,
    *,
    cwd: Path,
    runtime: ComposeRuntime = DEFAULT_COMPOSE_RUNTIME,
) -> bool:
    return is_compose_service_in_status(
        compose_file,
        service_name,
        "running",
        cwd=cwd,
        runtime=runtime,
    )


def has_compose_service_exited(
    compose_file: Path,
    service_name: str,
    *,
    cwd: Path,
    runtime: ComposeRuntime = DEFAULT_COMPOSE_RUNTIME,
) -> bool:
    return is_compose_service_in_status(
        compose_file,
        service_name,
        "exited",
        cwd=cwd,
        runtime=runtime,
    )


def cleanup_compose(
    compose_file: Path,
    *,
    cwd: Path,
    runtime: ComposeRuntime = DEFAULT_COMPOSE_RUNTIME,
) -> CommandResult:
    return run_command(
        *build_compose_command(
            compose_file,
            "down",
            "--volumes",
            "--remove-orphans",
            runtime=runtime,
        ),
        cwd=cwd,
    )
