from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from camera_smoke.artifacts import write_command_transcript, write_text_artifact
from camera_smoke.commands import CommandResult, run_command


def build_compose_command(compose_file: Path, *args: str) -> list[str]:
    return ["docker", "compose", "-f", str(compose_file), *args]


def get_compose_logs(compose_file: Path, *, cwd: Path) -> str:
    result = run_command(
        *build_compose_command(compose_file, "logs", "--no-color"), cwd=cwd
    )
    return result.stdout + result.stderr


def get_compose_ps(compose_file: Path, *, cwd: Path) -> CommandResult:
    return run_command(*build_compose_command(compose_file, "ps", "--all"), cwd=cwd)


def write_compose_diagnostics(
    results_dir: Path,
    compose_file: Path,
    metadata: Mapping[str, object],
    *,
    cwd: Path,
) -> None:
    write_text_artifact(results_dir, "compose.log", get_compose_logs(compose_file, cwd=cwd))
    write_command_transcript(
        results_dir,
        "compose-ps.txt",
        get_compose_ps(compose_file, cwd=cwd),
    )
    write_text_artifact(
        results_dir, "metadata.json", json.dumps(metadata, indent=2, sort_keys=True)
    )


def is_compose_service_in_status(
    compose_file: Path, service_name: str, status: str, *, cwd: Path
) -> bool:
    result = run_command(
        *build_compose_command(
            compose_file, "ps", "--status", status, "--services"
        ),
        cwd=cwd,
    )
    if result.returncode != 0:
        return False

    services = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return service_name in services


def is_compose_service_running(
    compose_file: Path, service_name: str, *, cwd: Path
) -> bool:
    return is_compose_service_in_status(compose_file, service_name, "running", cwd=cwd)


def has_compose_service_exited(
    compose_file: Path, service_name: str, *, cwd: Path
) -> bool:
    return is_compose_service_in_status(compose_file, service_name, "exited", cwd=cwd)


def cleanup_compose(compose_file: Path, *, cwd: Path) -> CommandResult:
    return run_command(
        *build_compose_command(compose_file, "down", "--volumes", "--remove-orphans"),
        cwd=cwd,
    )
