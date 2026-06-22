from __future__ import annotations

from pathlib import Path


def build_compose_command(compose_file: Path, *args: str) -> list[str]:
    return ["docker", "compose", "-f", str(compose_file), *args]
