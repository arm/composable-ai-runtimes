from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODEL = "gpt-4.1"


def load_task(path: str) -> dict:
    with (ROOT / path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def safe_repo_path(path: str) -> Path:
    resolved = (ROOT / path).resolve()
    resolved.relative_to(ROOT)
    return resolved


def rel_path(path: Path) -> str:
    return str(path.resolve().relative_to(ROOT))


def run_shell(command: str, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        shell=True,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
