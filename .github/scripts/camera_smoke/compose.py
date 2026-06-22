from __future__ import annotations

from pathlib import Path

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


def cleanup_compose(compose_file: Path, *, cwd: Path) -> CommandResult:
    return run_command(
        *build_compose_command(compose_file, "down", "--volumes", "--remove-orphans"),
        cwd=cwd,
    )
